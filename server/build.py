#!/usr/bin/python2
# -*- coding: utf-8 -*-
#
# Minimalistic build server.
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

from lxml import etree
import argparse
import datetime
import grp
import guestfs
import libvirt
import os
import random
import re
import shutil
import stat
import subprocess
import tempfile
import time
import uuid

BUILDER_SETTINGS = {
    # Debian Wheezy
    "debian-wheezy-x86": {
        'partition': 0,
        'log_tty'  : "/dev/ttyS1",
        'build_user':   "builder",
        "build_group":  "builder",
    },
    "debian-wheezy-x64": {
        'partition': 0,
        'log_tty'  : "/dev/ttyS1",
        'build_user':   "builder",
        "build_group":  "builder",
    },

    # Debian Jessie
    "debian-jessie-x86": {
        'partition': 0,
        'log_tty'  : "/dev/ttyS1",
        'build_user':   "builder",
        "build_group":  "builder",
    },
    "debian-jessie-x64": {
        'partition': 0,
        'log_tty'  : "/dev/ttyS1",
        'build_user':   "builder",
        "build_group":  "builder",
    },

    # Debian Stretch
    "debian-stretch-x86": {
        'partition': 0,
        'log_tty'  : "/dev/ttyS1",
        'build_user':   "builder",
        "build_group":  "builder",
    },
    "debian-stretch-x64": {
        'partition': 0,
        'log_tty'  : "/dev/ttyS1",
        'build_user':   "builder",
        "build_group":  "builder",
    },

    # Debian Sid
    "debian-sid-x86": {
        'partition': 0,
        'log_tty'  : "/dev/ttyS1",
        'build_user':   "builder",
        "build_group":  "builder",
    },
    "debian-sid-x64": {
        'partition': 0,
        'log_tty'  : "/dev/ttyS1",
        'build_user':   "builder",
        "build_group":  "builder",
    },

    # Archlinux
    "arch-x86": {
        'partition': 0,
        'log_tty'  : "/dev/ttyS1",
        'build_user':   "builder",
        "build_group":  "builder",
    },
    "arch-x64": {
        'partition': 0,
        'log_tty'  : "/dev/ttyS1",
        'build_user':   "builder",
        "build_group":  "builder",
    },

    # Mageia 4
    "mageia4-x86": {
        'partition': 0,
        'log_tty'  : "/dev/ttyS1",
        'build_user':   "build",
        "build_group":  "build",
    },
    "mageia4-x64": {
        'partition': 0,
        'log_tty'  : "/dev/ttyS1",
        'build_user':   "build",
        "build_group":  "build",
    },

    # Mageia 5
    "mageia5-x86": {
        'partition': 0,
        'log_tty'  : "/dev/ttyS1",
        'build_user':   "build",
        "build_group":  "build",
    },
    "mageia5-x64": {
        'partition': 0,
        'log_tty'  : "/dev/ttyS1",
        'build_user':   "build",
        "build_group":  "build",
    },

    # Fedora 22
    "fedora-22-x86": {
        'partition': "/dev/fedora/root",
        'log_tty'  : "/dev/ttyS0",
        'build_user':   "builder",
        "build_group":  "builder",
    },
    "fedora-22-x64": {
        'partition': "/dev/fedora/root",
        'log_tty'  : "/dev/ttyS0",
        'build_user':   "builder",
        "build_group":  "builder",
    },

    # Fedora 23
    "fedora-23-x86": {
        'partition': "/dev/fedora/root",
        'log_tty'  : "/dev/ttyS1",
        'build_user':   "builder",
        "build_group":  "builder",
    },
    "fedora-23-x64": {
        'partition': "/dev/fedora/root",
        'log_tty'  : "/dev/ttyS1",
        'build_user':   "builder",
        "build_group":  "builder",
    },

    # XUbuntu 14.04 with graphical environment
    "xubuntu-14.04-x86-gui": {
        'partition': 0,
        'log_tty'  : "/dev/ttyS1",
        'build_user':   "builder",
        "build_group":  "builder",
    },
}

BUILDER_ROOT = os.path.dirname(os.path.realpath(__file__))
assert os.path.isfile(os.path.join(BUILDER_ROOT, "buildjob.service"))
assert os.path.isfile(os.path.join(BUILDER_ROOT, "rc.local"))
assert os.path.isfile(os.path.join(BUILDER_ROOT, "wrapper.sh"))
assert os.path.isdir(os.path.join(BUILDER_ROOT, "./jobs"))

def try_mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            return False
        else:
            raise
    return True

def randomMAC():
    mac = [ 0x00, 0x16, 0x3e, random.randint(0x00, 0x7f),
            random.randint(0x00, 0xff), random.randint(0x00, 0xff) ]
    return ':'.join(map(lambda x: "%02x" % x, mac))

class BuildJob(object):
    def __init__(self, original):
        """ Create a new build job. """

        self.root           = None      # build directory
        self.log            = None      # Handle to build.log file
        self.vm_log_path    = None      # Serial port log, used for build log
        self.disks          = []        # Disk information
        self.domain         = None      # Domain
        self.settings       = None      # Various settings
        self.guestfs        = None      # GuestFs if started, else None

        try:
            self._initialize(original)
        except:
            self._destroy()
            raise

    def __del__(self):
        self._destroy()

    def _log_to_file(self, message):
        """ Writes a message to the log. """
        if self.log is not None:
            message = "[%s] %s" % (datetime.datetime.utcnow().strftime('%H:%M:%S'), message)
            self.log.write("%s\n" % (message,))
            self.log.flush()
            print message

    def _check_call(self, cmd, *args, **kwds):
        """ Call external process. """
        self._log_to_file("Running %s" % cmd)
        if self.log is not None:
            kwds['stdout'] = self.log
            kwds['stderr'] = subprocess.STDOUT
        return subprocess.check_call(cmd, *args, **kwds)

    def _call(self, cmd, *args, **kwds):
        """ Call external process. """
        self._log_to_file("Running %s" % cmd)
        if self.log is not None:
            kwds['stdout'] = self.log
            kwds['stderr'] = subprocess.STDOUT
        return subprocess.call(cmd, *args, **kwds)

    def _start_guestfs(self):
        """ Start guestfs for direct disk access. """
        if self.guestfs is None:
            self.guestfs = guestfs.GuestFS()
            self.guestfs.add_drive_opts(self.disks[0], format='qcow2', readonly=0)
            self.guestfs.launch()

            partition = self.settings['partition']
            if isinstance(partition, int):
                partition_list = self.guestfs.list_partitions()
                partition_name = partition_list[partition]
            else:
                partition_name = partition
            self.guestfs.mount_options("", partition_name, "/")

    def _initialize(self, original):
        """ Used in the constructor, initialize build job. """

        # Short path - if its not a whitelisted VM then abort immediately
        if not BUILDER_SETTINGS.has_key(original):
            raise RuntimeError("Original VM is not in the whitelist.")

        # Load settings, this contains the partition number and other information
        self.settings = BUILDER_SETTINGS[original]

        # Get group of libvirtd
        try:
            group = grp.getgrnam("libvirt-qemu")
        except KeyError:
            group = grp.getgrnam("libvirt")
        gid_libvirt = group.gr_gid

        # Create root directory
        self.root = tempfile.mkdtemp(prefix="build-", dir=os.path.join(BUILDER_ROOT, "./jobs"))
        os.chown(self.root, -1, gid_libvirt)
        os.chmod(self.root, 0775)

        # Open log file
        self.log = open(os.path.join(self.root, "build.log"), "ab", buffering=0)
        os.fchmod(self.log.fileno(), 0644) # no need to give it to libvirt
        self._log_to_file("Build started at %s" % datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))
        self._log_to_file("Cloning VM %s for build job %s" % (original, self.root))

        # Get information from original VM, create new domain name
        xml  = subprocess.check_output(["virsh", "dumpxml", "--domain", original])
        tree = etree.fromstring(xml)
        domain = "%s-%s" % (os.path.basename(self.root), original)
        assert domain.startswith("build-")

        # Update name / uuid / mac
        xml_name = tree.xpath("/domain/name")[0]
        xml_name.text = domain
        xml_uuid = tree.xpath("/domain/uuid")[0]
        xml_uuid.text = str(uuid.uuid1())
        xml_mac = tree.xpath("/domain/devices/interface[@type='network']/mac")[0]
        xml_mac.set('address', randomMAC())

        # Clone disks
        for i, xml_disk in enumerate(tree.xpath("/domain/devices/disk[@device='disk']/source")):
            if not xml_disk.get("file").endswith(".qcow2"):
                raise RuntimeError("Wrong disk file format, only qcow2 is supported.")
            disk_path = os.path.abspath(os.path.join(self.root, "disk%d.qcow2" % i))
            self._check_call(["qemu-img", "create", "-f", "qcow2", "-b", xml_disk.get("file"), disk_path])
            os.chown(disk_path, -1, gid_libvirt)
            os.chmod(disk_path, 0660) # disk image should be protected
            xml_disk.set("file", disk_path)
            self.disks.append(disk_path)
        assert len(self.disks) > 0

        # Define a serial port for the log - undocumented,
        # but based on the qemu source this works. ;)
        self.vm_log_path = os.path.abspath(os.path.join(self.root, "vm_log"))
        os.mkfifo("%s.out" % self.vm_log_path)
        os.chown("%s.out" % self.vm_log_path, -1, gid_libvirt)
        os.chmod("%s.out" % self.vm_log_path, 0660)
        os.symlink("/dev/null", "%s.in" % self.vm_log_path)
        xml_serial = etree.SubElement(tree.xpath("/domain/devices")[0], "serial", type="pipe")
        etree.SubElement(xml_serial, "source", path=self.vm_log_path)
        etree.SubElement(xml_serial, "target", port="1")

        # Audio support
        if original.endswith("-gui"):
            qemu_namespace = "http://libvirt.org/schemas/domain/qemu/1.0"
            etree.register_namespace("qemu", qemu_namespace);
            xml_qemu = etree.SubElement(tree.xpath("/domain")[0], "{%s}commandline" % qemu_namespace)
            etree.SubElement(xml_qemu, "{%s}env" % qemu_namespace, name="QEMU_AUDIO_DRV", value="none")

        # Define new VM based on modified XML file
        xml_path = os.path.join(self.root, "definition.xml")
        with open(xml_path, "wb") as fp:
            fp.write(etree.tostring(tree, pretty_print=True))
        os.chown(xml_path, -1, gid_libvirt)
        os.chmod(xml_path, 0664)
        self._check_call(["virsh", "define", xml_path])
        self.domain = domain

        self._log_to_file("Initialized build job %s" % self.root)

    def _destroy(self):
        """ Deinitialize build job """

        self._log_to_file("Deleting build job %s" % self.root)
        if self.domain is not None:  # Delete domain
            self._call(["virsh", "destroy", self.domain])
            self._check_call(["virsh", "undefine", self.domain])
            self.domain = None
        if self.guestfs is not None: # Unmount guestfs
            self.guestfs.close()
            self.guestfs = None
        if self.log is not None:     # Close log file if any
            self.log.close()
            self.log = None
        if self.root is not None:    # Delete root directory
            shutil.rmtree(self.root)
            self.root = None
        return True

    def _forward_log(self):
        """ Forward log from VM to log file """

        if self.log is None:
            return

        fd = None
        try:
            fd = os.open("%s.out" % self.vm_log_path, os.O_RDONLY)
            data = ""
            while True:
                new_data = os.read(fd, 4096)
                if new_data == "":
                    self._log_to_file(data)
                    return

                data += new_data
                lines = data.split("\n")
                for line in lines[:-1]:
                    self._log_to_file(line)
                data = lines[-1]

        finally:
            if fd is not None:
                os.close(fd)

    def _wait(self):
        """ Wait until a VM is really dead """
        conn = None
        try:
            conn = libvirt.open("qemu:///system")
            while True:
                time.sleep(10)
                try:
                    state = conn.lookupByName(self.domain).info()[0]
                except (libvirt.libvirtError, TypeError, IndexError):
                    break
                if state in [4, 5, 6]: # crashed or shutdown
                    break
        finally:
            if conn is not None:
                conn.close()

    #
    # File system functions
    #

    def fs_ls(self, path):
        self._start_guestfs()
        return self.guestfs.ls(path)

    def fs_exists(self, path):
        self._start_guestfs()
        return self.guestfs.exists(path)

    def fs_is_file(self, path):
        self._start_guestfs()
        return self.guestfs.is_file(path)

    def fs_is_dir(self, path):
        self._start_guestfs()
        return self.guestfs.is_dir(path)

    def fs_cp(self, src, dest):
        self._start_guestfs()
        self._log_to_file("Copying %s -> %s" % (src, dest))
        return self.guestfs.cp(src, dest)

    def fs_mv(self, src, dest):
        self._start_guestfs()
        self._log_to_file("Moving %s -> %s" % (src, dest))
        return self.guestfs.mv(src, dest)

    def fs_ln_s(self, src, dest):
        self._start_guestfs()
        self._log_to_file("Symlinking %s -> %s" % (src, dest))
        return self.guestfs.ln_s(src, dest)

    def fs_chmod(self, path, mode):
        self._start_guestfs()
        return self.guestfs.chmod(mode, path)

    def fs_chown(self, path, uid, gid):
        self._start_guestfs()
        return self.guestfs.chown(uid, gid, path)

    def fs_mkdir_p(self, path):
        self._start_guestfs()
        self._log_to_file("Creating directory %s" % (path,))
        return self.guestfs.mkdir_p(path)

    def fs_upload_file(self, path, local_path):
        self._start_guestfs()
        self._log_to_file("Uploading %s into VM" % (path,))
        # Note - we do not check if it already exists
        return self.guestfs.upload(local_path, path)

    def fs_upload_content(self, path, content):
        self._start_guestfs()
        self._log_to_file("Uploading %s into VM" % (path,))
        fp = None
        try:
            fp = tempfile.NamedTemporaryFile(prefix="upload-", dir=self.root, delete=False)
            fp.write(content)
            fp.close()
            return self.guestfs.upload(fp.name, path)
        finally:
            if fp is not None:
                os.unlink(fp.name)

    def fs_upload_recursive(self, path, local_path):
        if os.path.isfile(local_path):
            assert not self.fs_exists(path)
            self.fs_upload_file(path, local_path)

        elif os.path.isdir(local_path):
            self.fs_mkdir_p(path)
            for f in os.listdir(local_path):
                self.fs_upload_recursive("%s/%s" % (path, f), os.path.join(local_path, f))

        else:
            raise NotImplementedError("Failed to upload %s, neither a file nor directory" % local_path)

        # Copy file permissions to make sure we don't remove execute permissions
        permissions = os.stat(local_path)[stat.ST_MODE]
        self.fs_chmod(path, permissions)

    def fs_download_file(self, path, local_path):
        self._start_guestfs()
        assert not os.path.exists(local_path)
        return self.guestfs.download(path, local_path)

    def fs_download_content(self, path):
        self._start_guestfs()
        fp = None
        try:
            fp = tempfile.NamedTemporaryFile(prefix="download-", dir=self.root, delete=False)
            fp.close()
            self.guestfs.download(path, fp.name)
            with open(fp.name, "rb") as fp2:
                return fp2.read()
        finally:
            if fp is not None:
                os.unlink(fp.name)

    def fs_download_recursive(self, path, local_path):
        if self.fs_is_file(path):
            assert not os.path.exists(local_path)
            self.fs_download_file(path, local_path)

        elif self.fs_is_dir(path):
            try_mkdir_p(local_path)
            for f in self.fs_ls(path):
                self.fs_download_recursive("%s/%s" % (path, f), os.path.join(local_path, f))

        else:
            raise NotImplementedError("Failed to download %s, neither a file nor directory" % path)

    #
    # VM control functions
    #

    def run(self):
        if self.guestfs:
            self.guestfs.close()
            self.guestfs = None
            time.sleep(5) # make sure the guestfs mount is really gone

        self._check_call(["virsh", "start", self.domain])
        self._forward_log()
        self._log_to_file("Connection to VM lost, waiting for VM to shutdown")
        self._wait()
        self._call(["virsh", "destroy", self.domain])

    def build(self):
        if not self.fs_is_file("/build/source/boot.sh"):
            raise RuntimeError("Unable to find /build/source/boot.sh in VM")

        assert not self.fs_exists("/build/wrapper.sh")
        assert not self.fs_exists("/build/status")
        assert not self.fs_exists("/build/log")

        if self.fs_exists("/usr/bin/systemctl") or self.fs_exists("/bin/systemctl"):
            assert not self.fs_exists("/usr/lib/systemd/user/buildjob.service")
            assert not self.fs_exists("/etc/systemd/system/multi-user.target.wants/buildjob.service")
            assert self.fs_is_dir("/etc/systemd/system/multi-user.target.wants")

            self._log_to_file("Using systemd based startup sequence")
            self.fs_mkdir_p("/usr/lib/systemd/user")
            self.fs_upload_file("/usr/lib/systemd/user/buildjob.service",
                                os.path.join(BUILDER_ROOT, "buildjob.service"))
            self.fs_ln_s("/usr/lib/systemd/user/buildjob.service",
                         "/etc/systemd/system/multi-user.target.wants/buildjob.service")

        elif self.fs_exists("/etc/rc.local"):
            self._log_to_file("Using rc.local based startup sequence")
            self.fs_upload_file("/etc/rc.local", os.path.join(BUILDER_ROOT, "rc.local"))
            self.fs_chmod("/etc/rc.local", 0755)

        else:
            raise NotImplementedError("System is using a non-supported init mechanism")

        # Upload wrapper script and make executable
        with open(os.path.join(BUILDER_ROOT, "wrapper.sh"), 'rb') as fp:
            wrapper = fp.read()

        wrapper = re.sub("^LOG_TTY=\".*\"$",
                         "LOG_TTY=\"%s\"" % self.settings["log_tty"],
                         wrapper, flags=re.MULTILINE)

        wrapper = re.sub("^BUILD_USER=\".*\"$",
                         "BUILD_USER=\"%s\"" % self.settings["build_user"],
                         wrapper, flags=re.MULTILINE)

        wrapper = re.sub("^BUILD_GROUP=\".*\"$",
                         "BUILD_GROUP=\"%s\"" % self.settings["build_group"],
                         wrapper, flags=re.MULTILINE)

        self.fs_upload_content("/build/wrapper.sh", wrapper)
        self.fs_chmod("/build/wrapper.sh", 0755)
        self.fs_chmod("/build/source/boot.sh", 0755)

        # Run the actual build
        self.run()

        # Check the status of the build
        if not self.fs_is_file("/build/status"):
            raise RuntimeError("Unable to determine status, build was aborted?")

        status = int(self.fs_download_content("/build/status"))
        if status != 0:
            raise RuntimeError("Build exited with status code %d" % status)

    def prepare(self, local_path, local_deps=None):
        assert os.path.isdir(local_path)
        assert os.path.isfile(os.path.join(local_path, "boot.sh"))
        self.fs_upload_recursive("/build/source", local_path)
        assert self.fs_is_file("/build/source/boot.sh")

        if local_deps is not None:
            assert os.path.isdir(local_deps)
            self.fs_upload_recursive("/build/source/deps", local_deps)

    def publish(self, local_path):
        assert os.path.isdir(local_path)
        assert not os.path.exists(os.path.join(local_path, "internal_build.log"))
        assert not os.path.exists(os.path.join(local_path, "SHA256SUMS"))
        assert not os.path.exists(os.path.join(local_path, "MD5SUMS"))

        shutil.copyfile(os.path.join(self.root, "build.log"),
                        os.path.join(local_path, "internal_build.log"))

        self.fs_download_file("/build/log", os.path.join(local_path, "build.log"))

        filelist = ["internal_build.log", "build.log"]

        for f in self.fs_ls("/build"):
            if f in ["wrapper.sh", "source", "log"]:
                continue

            elif self.fs_is_file("/build/%s" % f):
                self.fs_download_file("/build/%s" % f, os.path.join(local_path, f))
                filelist.append(f)

            else:
                self._log_to_file("Skipping download of directory %s" % f)

        with open(os.path.join(local_path, "SHA256SUMS"), "wb") as fp:
            subprocess.check_call(["sha256sum", "--"] + filelist, cwd=local_path,
                                  stdout=fp, stderr=subprocess.STDOUT)

        with open(os.path.join(local_path, "MD5SUMS"), "wb") as fp:
            subprocess.check_call(["md5sum", "--"] + filelist, cwd=local_path,
                                  stdout=fp, stderr=subprocess.STDOUT)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Minimalistic build server")
    parser.add_argument('--machine', help="Select build VM", required=True)
    parser.add_argument('--dependencies', help="Additional build dependencies", default=None)
    parser.add_argument('source', help="Source directory to process")
    parser.add_argument('destination', help="Destination directory")
    args = parser.parse_args()

    if not BUILDER_SETTINGS.has_key(args.machine):
        raise RuntimeError("%s is not a supported VM" % args.machine)

    if not os.path.isdir(args.source):
        raise RuntimeError("%s is not a directory" % args.source)

    if not os.path.isdir(args.destination):
        raise RuntimeError("%s is not a directory" % args.destination)

    if len(os.listdir(args.destination)):
        raise RuntimeError("%s is not empty, refusing to build" % args.destination)

    job = None
    try:
        job = BuildJob(args.machine)
        job.prepare(args.source, args.dependencies)
        job.build()
        job.publish(args.destination)
    finally:
        if job is not None:
            job._destroy()

    exit(0)
