#!/bin/bash
#
# Script to start a builds for Wine development version.
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

VERSION="1.9.16"
RELEASE=""

mkdir -p "repository/raw/macosx-wine-development"
repo_path="repository/raw/macosx-wine-development/$VERSION$RELEASE-x86"
[ -d "$repo_path" ] && rmdir --ignore-fail-on-non-empty "$repo_path"
if mkdir "$repo_path"; then
	./server/build.py --machine "debian-stretch-x64" \
		--dependencies "repository/raw/macosx-toolchain-2.0.0/deps" \
		"temp/macosx-wine-development" "$repo_path"
fi

for codename in stretch wheezy jessie sid; do
	mkdir -p "repository/raw/debian-$codename-development"
	for arch in x86 x64; do

		repo_path="repository/raw/debian-$codename-development/$VERSION$RELEASE-$arch"
		[ -d "$repo_path" ] && rmdir --ignore-fail-on-non-empty "$repo_path"
		if mkdir "$repo_path"; then
			./server/build.py --machine "debian-$codename-$arch" \
				"temp/debian-$codename-development" "$repo_path"
		fi

	done
done

for codename in 5 4; do
	mkdir -p "repository/raw/mageia-$codename-development"
	for arch in x86 x64; do

		repo_path="repository/raw/mageia-$codename-development/$VERSION$RELEASE-$arch"
		[ -d "$repo_path" ] && rmdir --ignore-fail-on-non-empty "$repo_path"
		if mkdir "$repo_path"; then
			./server/build.py --machine "mageia$codename-$arch" \
				"temp/mageia-any-development" "$repo_path"
		fi

	done
done

for codename in 22 23 24; do
	mkdir -p "repository/raw/fedora-$codename-development"
	for arch in x86 x64; do

		repo_path="repository/raw/fedora-$codename-development/$VERSION$RELEASE-$arch"
		[ -d "$repo_path" ] && rmdir --ignore-fail-on-non-empty "$repo_path"
		if mkdir "$repo_path"; then
			./server/build.py --machine "fedora-$codename-$arch" \
				"temp/fedora-any-development" "$repo_path"
		fi

	done
done
