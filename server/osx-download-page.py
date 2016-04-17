#!/usr/bin/python2
# -*- coding: utf-8 -*-
#
# Update overview page for OSX downloads.
#
# Copyright (C) 2015-2016 Sebastian Lackner
# Copyright (C) 2015-2016 Michael Müller
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

import collections
import locale
import os
import re
import sys
import time
import pytz
import datetime

def process_template(filename, namespace):
    content_blocks = []
    compiled = ["global __filename"]
    controlstack = []
    only_control = False

    with open(filename, 'r') as fp:
        content = fp.read()

    for i, block in enumerate(re.split("{{(.*?)}}", content, flags=re.DOTALL)):
        if i % 2 == 0:
            if only_control and block.startswith("\n"):
                block = block[1:]
            if block == "":
                only_control = True
                continue
            indent = "    " * len(controlstack)
            content_blocks.append(block)
            compiled.append("%s__result.append(__content_blocks[%d])" %
                            (indent, len(content_blocks) - 1))
            only_control = block.endswith("\n")

        else:
            for line in block.split("\n"):
                line = line.strip()
                indent = "    " * len(controlstack)
                assert not line.endswith("\\")

                if line.startswith("if "):
                    compiled.append("%sif %s:" % (indent, line[3:]))
                    controlstack.append("if")

                elif line.startswith("elif "):
                    assert controlstack[-1] == "if"
                    compiled.append("%spass" % (indent,))
                    compiled.append("%selif %s:" %
                                    ("    " * (len(controlstack) - 1), line[5:]))

                elif line == "else":
                    assert controlstack[-1] == "if"
                    compiled.append("%spass" % (indent,))
                    compiled.append("%selse:" % ("    " * (len(controlstack) - 1),))

                elif line == "endif":
                    assert controlstack.pop() == "if"
                    compiled.append("%spass" % (indent,))

                elif line.startswith("for "):
                    compiled.append("%sfor %s:" % (indent, line[4:]))
                    controlstack.append("for")

                elif line == "endfor":
                    assert controlstack.pop() == "for"
                    compiled.append("%spass" % (indent,))

                elif line.startswith("while "):
                    compiled.append("%swhile %s:" % (indent, line[6:]))
                    controlstack.append("while")

                elif line == "endwhile":
                    assert controlstack.pop() == "while"
                    compiled.append("%spass" % (indent,))

                elif line.startswith("print "):
                    compiled.append("%s__result.append(%s)" % (indent, line[6:]))

                elif line.startswith("="):
                    compiled.append("%s__result.append(%s)" % (indent, line[1:]))

                elif not line.startswith("#"):
                    compiled.append("%s%s" % (indent, line))

    assert len(controlstack) == 0

    if not namespace.has_key("__filename"):
        namespace["__filename"] = os.path.basename(filename)

    local_namespace = {
        "include"          : lambda x: process_template(os.path.join(os.path.dirname(filename), x), namespace),
        "__content_blocks" : content_blocks,
        "__result"         : [],
    }

    exec "\n".join(compiled) in namespace, local_namespace
    return "".join(local_namespace["__result"])

def parse_subversion(v):
    for i, c in enumerate(re.split("([0-9]+)", v)):
        if i % 2 == 0: yield c
        else: yield int(c)

def parse_version(v):
    for i, c in enumerate(re.split("([-.~])", v)):
        if i % 2 == 0: yield tuple(parse_subversion(c))
        else: yield {".": 2, "-": 1, "~": -1}[c]
    yield 0

def load_packages(repository):
    packages = {}

    for filename in os.listdir(repository):
        full_path = os.path.join(repository, filename)
        if not filename.endswith(".pkg"): continue
        if not os.path.isfile(full_path): continue

        parts = filename[:-4].split("-")
        for i in xrange(1, len(parts)):
            version = "-".join(parts[i:])
            if re.match("^[0-9]+([-.~][a-z]*[0-9]+)*$", version) is None: continue
            name = "-".join(parts[:i])
            if not packages.has_key(name): packages[name] = []
            packages[name].append((filename, name, version, tuple(parse_version(version))))
            break

    return packages

def load_sha256sums(repository):
    checksums = {}

    if os.path.exists(os.path.join(repository, "SHA256SUMS")):
        with open(os.path.join(repository, "SHA256SUMS"), "r") as fp:
            for line in fp:
                sha, f = line.rstrip().split("  ", 1)
                checksums[f] = sha

    return checksums

def update_template(repository):
    packages   = load_packages(os.path.join(repository, "i686"))
    sha256sums = load_sha256sums(os.path.join(repository, "i686"))

    # Get list of all current packages
    pkg_packages = []
    tar_packages = []

    for name, pkg_name, tar_name in [("winehq-devel",
                                        "<b>Installer for \"Wine Development\"</b>",
                                        "Tarball for \"Wine Development\""),
                                     ("winehq-staging",
                                        "<b>Installer for \"Wine Staging\"</b>",
                                        "Tarball for \"Wine Staging\"")]:
        if not packages.has_key(name): continue
        candidates = packages[name]
        candidates.sort(key=lambda x: x[3], reverse=True)
        base_filename, _, version, _ = packages[name][0]

        # installer
        filename = base_filename
        full_path = os.path.join(repository, "i686", filename)
        size = (os.path.getsize(full_path) + 1024 * 1024 / 2) / (1024 * 1024)
        pkg_packages.append({ "name":       pkg_name,
                              "filename":   os.path.join("i686", filename),
                              "sha256":     sha256sums[filename],
                              "version":    version,
                              "size":       "%dM" % size })

        # tarball (32-bit)
        filename = "portable-%s-osx.tar.gz" % base_filename[:-4]
        full_path = os.path.join(repository, "i686", filename)
        if os.path.isfile(full_path):
            size = (os.path.getsize(full_path) + 1024 * 1024 / 2) / (1024 * 1024)
            tar_packages.append({ "name":       "%s (32-bit)" % tar_name,
                                  "filename":   os.path.join("i686", filename),
                                  "sha256":     sha256sums[filename],
                                  "version":    version,
                                  "size":       "%dM" % size })

        # tarball (64-bit)
        filename = "portable-%s-osx64.tar.gz" % base_filename[:-4]
        full_path = os.path.join(repository, "i686", filename)
        if os.path.isfile(full_path):
            size = (os.path.getsize(full_path) + 1024 * 1024 / 2) / (1024 * 1024)
            tar_packages.append({ "name":       "%s (64-bit)" % tar_name,
                                  "filename":   os.path.join("i686", filename),
                                  "sha256":     sha256sums[filename],
                                  "version":    version,
                                  "size":       "%dM" % size })

    # Get list of all subdirectories
    timezone = pytz.timezone("Etc/GMT+6")
    subdirectories = []
    for name in os.listdir(repository):
        full_path = os.path.join(repository, name)
        if not os.path.isdir(full_path): continue
        modified = datetime.datetime.fromtimestamp(os.path.getmtime(full_path), timezone)
        subdirectories.append({ "name": name,
                                "modified": modified.strftime("%d-%b-%Y %H:%M") })

    # Update download file
    script_dir = os.path.dirname(os.path.realpath(__file__))
    namespace = { "pkg_packages": pkg_packages,
                  "tar_packages": tar_packages,
                  "subdirectories": subdirectories }
    content = process_template(os.path.join(script_dir, "osx-template.html"), namespace)
    with open(os.path.join(repository, "download.html"), 'w') as fp:
        fp.write(content)

if __name__ == "__main__":

    try:
        repository = sys.argv[1]
    except IndexError:
        raise RuntimeError("Expected path to repository (without i686 subdirectory)")

    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    update_template(repository)
