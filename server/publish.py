#!/usr/bin/python2
# -*- coding: utf-8 -*-
#
# Tool to publish packages to a repository.
#
# Copyright (C) 2014-2015 Sebastian Lackner
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA
#

import argparse
import errno
import hashlib
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time

BUILDER_SIGNKEY = "5FCBF54A"
BUILDER_TOOLS   = os.path.join(os.path.dirname(os.path.realpath(__file__)), "./tools")
assert os.path.isdir(os.path.join(BUILDER_TOOLS, "bin"))
assert os.path.isdir(os.path.join(BUILDER_TOOLS, "lib/x86_64-linux-gnu/perl5/5.20"))
assert os.path.isdir(os.path.join(BUILDER_TOOLS, "share/perl5"))
assert os.path.isfile(os.path.expanduser("~/.rpmmacros")) # ln -s $(pwd)/rpmmacros ~/.rpmmacros

def try_mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            return False
        else:
            raise
    return True

def check_output_with_input(*popenargs, **kwargs):
    if 'stdout' in kwargs or 'stdin' in kwargs:
        raise ValueError('stdout/stdin argument not allowed')

    input = kwargs['input']
    del kwargs['input']

    process = subprocess.Popen(stdout=subprocess.PIPE, stdin=subprocess.PIPE, *popenargs, **kwargs)
    output, unused_err = process.communicate(input)
    retcode = process.poll()

    if retcode:
        cmd = kwargs.get("args")
        if cmd is None:
            cmd = popenargs[0]
        error = subprocess.CalledProcessError(retcode, cmd)
        error.output = output
        raise error

    return output

class DirectoryLock(object):
    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.lock = "/tmp/builder-%s.lock" % hashlib.md5(self.path).hexdigest()
    def __enter__(self):
        while not try_mkdir_p(self.lock):
            time.sleep(0.5)
    def __exit__(self, type, value, traceback):
        os.rmdir(self.lock)
        return False

def publish(local_path, repository, signkey):

    # Determine status of build
    status_file = os.path.join(local_path, "status")
    if os.path.exists(status_file):
        status = int(open(status_file, "r").read())
    else:
        status = 100

    if status != 0:
        raise RuntimeError("Build failed, not pushing to repository")

    packages_deb        = []
    packages_rpm        = []
    packages_archlinux  = []
    packages_macos      = []

    for f in os.listdir(local_path):
        if os.path.isfile(os.path.join(local_path, f)):
            if f.endswith(".deb"):
                packages_deb.append(f)
            elif f.endswith(".rpm"):
                packages_rpm.append(f)
            elif f.endswith(".pkg.tar.xz"):
                packages_archlinux.append(f)
            elif re.match("^.*-osx([0-9]+(\\.[0-9]+)?)?\\.pkg$", f):
                packages_macos.append(f)

    # needed for repo-add / genhdlist2
    def _preexec_fn():
        os.environ["PATH"] += ":%s" % os.path.join(BUILDER_TOOLS, "bin")
        os.environ["PERL5LIB"] = "%s:%s" % (os.path.join(BUILDER_TOOLS, "lib/x86_64-linux-gnu/perl5/5.20"),
                                            os.path.join(BUILDER_TOOLS, "share/perl5"))

    # needed for rpm
    def _preexec_fn_setsid():
        _preexec_fn()
        os.setsid()

    if repository.endswith("/"):
        repository = repository[:-1]

    # Update the repository
    if re.match("^(.*/)?debian$", repository):
        assert len(packages_deb)        > 0
        assert len(packages_rpm)        == 0
        assert len(packages_archlinux)  == 0
        assert len(packages_macos)      == 0

        # Get codename from package files
        codename = None
        for f in packages_deb:
            print f
            m = re.match("^(.*)~(.*)_(i386|amd64)\\.deb$", f)
            assert m is not None
            if codename is None:
                codename = m.group(2)
            assert codename == m.group(2)

        # Validate codename and repository path
        assert codename in ["wheezy", "jessie", "stretch", "sid"]
        assert os.path.isdir(repository)
        assert os.path.isfile("%s/conf/distributions" % repository)

        # Make sure SignWith: lines reference the same key
        with open("%s/conf/distributions" % repository) as fp:
            for line in fp:
                if not ":" in line: continue
                k, v = line.rstrip("\n").split(":", 1)
                if k.strip().lower() == "signwith":
                    assert v.strip().lower() == signkey.lower()

        temppath = tempfile.mkdtemp()
        try:
            for f in packages_deb:
                shutil.copy(os.path.join(local_path, f), temppath)
                subprocess.check_call(["dpkg-sig", "--sign", "builder", "-k",
                                       signkey, os.path.join(temppath, f)])

            with DirectoryLock(repository):
                for f in packages_deb:
                    subprocess.check_call(["reprepro", "-b", repository, "includedeb",
                                           codename, os.path.join(temppath, f)])

        finally:
            shutil.rmtree(temppath)

    elif re.match("^(.*/)?arch/(x86_64|i686)$", repository):
        assert len(packages_deb)        == 0
        assert len(packages_rpm)        == 0
        assert len(packages_archlinux)  > 0
        assert len(packages_macos)      == 0

        # Create repository path if it doesn't exist
        try_mkdir_p(repository)

        temppath = tempfile.mkdtemp()
        try:
            for f in packages_archlinux:
                shutil.copy(os.path.join(local_path, f), temppath)
                subprocess.check_call(["gpg", "--detach-sign", "-u", signkey,
                                       "--no-armor", os.path.join(temppath, f)])

            with DirectoryLock(repository):
                for f in packages_archlinux:
                    if os.path.isfile(os.path.join(repository, f)) or \
                       os.path.isfile(os.path.join(repository, "%s.sig" % f)):
                        raise RuntimeError("new package would overwrite existing one")

                for f in packages_archlinux:
                    shutil.copy(os.path.join(temppath, f), repository)
                    shutil.copy(os.path.join(temppath, "%s.sig" % f), repository)

                for f in packages_archlinux:
                    subprocess.check_call(["repo-add", "-v", "-s", "-k", signkey,
                                           "-d", "-f", os.path.join(repository, "winehq.db.tar.gz"),
                                           os.path.join(repository, f)], preexec_fn=_preexec_fn)

        finally:
            shutil.rmtree(temppath)

    elif re.match("^(.*/)?mageia/[0-9]+$", repository):
        assert len(packages_deb)        == 0
        assert len(packages_rpm)        > 0
        assert len(packages_archlinux)  == 0
        assert len(packages_macos)      == 0

        # Make sure packages contain architecture
        sub_repositories = set()
        for f in packages_rpm:
            m = re.match("^(.*)\\.(i586|x86_64)\\.rpm$", f)
            assert m is not None
            sub_repositories.add(m.group(2))

        # Create repository path if it doesn't exist
        for d in sub_repositories:
            try_mkdir_p(os.path.join(repository, d))

        temppath = tempfile.mkdtemp()
        try:
            for f in packages_rpm:
                shutil.copy(os.path.join(local_path, f), temppath)
                check_output_with_input(["rpm", "--addsign", os.path.join(temppath, f)],
                                        input="\n\n", preexec_fn=_preexec_fn_setsid)

            with DirectoryLock(repository):
                for f in packages_rpm:
                    d = re.match("^(.*)\\.(i586|x86_64)\\.rpm$", f).group(2)
                    if os.path.isfile(os.path.join(os.path.join(repository, d), f)):
                        raise RuntimeError("new package would overwrite existing one")

                for f in packages_rpm:
                    d = re.match("^(.*)\\.(i586|x86_64)\\.rpm$", f).group(2)
                    shutil.copy(os.path.join(temppath, f), os.path.join(repository, d))

                for d in sub_repositories:
                    subprocess.check_call(["genhdlist2", "--xml-info", os.path.join(repository, d)],
                                          preexec_fn=_preexec_fn)

        finally:
            shutil.rmtree(temppath)

    elif re.match("^(.*/)?fedora/[0-9]+$", repository):
        assert len(packages_deb)        == 0
        assert len(packages_rpm)        > 0
        assert len(packages_archlinux)  == 0
        assert len(packages_macos)      == 0

        # Make sure packages contain architecture
        sub_repositories = set()
        for f in packages_rpm:
            m = re.match("^(.*)\\.(i686|x86_64)\\.rpm$", f)
            assert m is not None
            sub_repositories.add(m.group(2))

        # Create repository path if it doesn't exist
        for d in sub_repositories:
            try_mkdir_p(os.path.join(repository, d))

        temppath = tempfile.mkdtemp()
        try:
            for f in packages_rpm:
                shutil.copy(os.path.join(local_path, f), temppath)
                check_output_with_input(["rpm", "--addsign", os.path.join(temppath, f)],
                                        input="\n\n", preexec_fn=_preexec_fn_setsid)

            with DirectoryLock(repository):
                for f in packages_rpm:
                    d = re.match("^(.*)\\.(i686|x86_64)\\.rpm$", f).group(2)
                    if os.path.isfile(os.path.join(os.path.join(repository, d), f)):
                        raise RuntimeError("new package would overwrite existing one")

                for f in packages_rpm:
                    d = re.match("^(.*)\\.(i686|x86_64)\\.rpm$", f).group(2)
                    shutil.copy(os.path.join(temppath, f), os.path.join(repository, d))

                subprocess.check_call(["createrepo", repository], preexec_fn=_preexec_fn)
                subprocess.check_call(["gpg", "--yes", "--detach-sign", "-u", signkey,
                                       "--armor", os.path.join(repository, "repodata/repomd.xml")])

        finally:
            shutil.rmtree(temppath)

    elif re.match("^(.*/)?macosx/i686", repository):
        assert len(packages_deb)        == 0
        assert len(packages_rpm)        == 0
        assert len(packages_archlinux)  == 0
        assert len(packages_macos)      > 0

        # Create repository path if it doesn't exist
        try_mkdir_p(repository)

        temppath = tempfile.mkdtemp()
        try:
            for f in packages_macos:
                shutil.copy(os.path.join(local_path, f), temppath)
                subprocess.check_call(["gpg", "--detach-sign", "-u", signkey,
                                       "--no-armor", os.path.join(temppath, f)])
                filelist = [f, "%s.sig" % f]
                with open(os.path.join(temppath, "%s.txt" % f), "wb") as fp:
                    fp.write("SHA256SUMS:\n")
                    fp.flush()
                    subprocess.check_call(["sha256sum", "--"] + filelist, cwd=temppath,
                                          stdout=fp, stderr=subprocess.STDOUT)
                    fp.write("\n")
                    fp.write("MD5SUMS:\n")
                    fp.flush()
                    subprocess.check_call(["md5sum", "--"] + filelist, cwd=temppath,
                                          stdout=fp, stderr=subprocess.STDOUT)

            with DirectoryLock(repository):
                for f in packages_macos:
                    if os.path.isfile(os.path.join(repository, f)) or \
                       os.path.isfile(os.path.join(repository, "%s.sig" % f)) or \
                       os.path.isfile(os.path.join(repository, "%s.txt" % f)):
                        raise RuntimeError("new package would overwrite existing one")

                for f in packages_macos:
                    shutil.copy(os.path.join(temppath, f), repository)
                    shutil.copy(os.path.join(temppath, "%s.sig" % f), repository)
                    shutil.copy(os.path.join(temppath, "%s.txt" % f), repository)

        finally:
            shutil.rmtree(temppath)

    else:
        raise NotImplementedError("Publishing for repository %s not defined" % repository)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tool to publish packages to a repository")
    parser.add_argument('--signkey', help="Sign key", default=BUILDER_SIGNKEY)
    parser.add_argument('source', help="Source directory to process")
    parser.add_argument('destination', help="Destination repository")
    args = parser.parse_args()

    if not os.path.isdir(args.source):
        raise RuntimeError("%s is not a directory" % args.source)

    publish(args.source, args.destination, args.signkey)
    exit(0)
