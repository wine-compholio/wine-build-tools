#!/bin/bash
#
# Script to build tools for OSX.
#
# Copyright (C) 2015 Sebastian Lackner
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

set -eux

VERSION="1.0.0"

deps_path="repository/raw/macosx-toolchain-$VERSION/deps"
mkdir -p "$deps_path"

# Compile native tools
mkdir -p "repository/raw/macosx-toolchain-$VERSION/tool"
for tool in clang bomutils cctools xar; do
	repo_path="repository/raw/macosx-toolchain-$VERSION/tool/$tool"
	[ -d "$repo_path" ] && rmdir --ignore-fail-on-non-empty "$repo_path"
	if mkdir "$repo_path"; then
		./server/build.py --machine "debian-jessie-x86" --dependencies "$deps_path" \
		"temp/macosx-$tool-native" "$repo_path"
		cp -a "$repo_path"/*.deb "$deps_path"
	fi
done

# Compile dependencies
mkdir -p "repository/raw/macosx-toolchain-$VERSION/package"
for package in libjpeg-turbo liblzma libtiff liblcms2 libxml2 libxslt libopenal-soft libtxc-dxtn-s2tc; do
	repo_path="repository/raw/macosx-toolchain-$VERSION/package/$package"
	[ -d "$repo_path" ] && rmdir --ignore-fail-on-non-empty "$repo_path"
	if mkdir "$repo_path"; then
		./server/build.py --machine "debian-jessie-x86" --dependencies "$deps_path" \
		"temp/macosx-$package" "$repo_path"
		cp -a "$repo_path"/*-osx.tar.gz "$deps_path"
	fi
done
