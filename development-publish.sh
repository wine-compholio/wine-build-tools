#!/bin/bash
#
# Script to publish builds for Wine development version.
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

VERSION="1.9.0"
RELEASE=""

repo_path="repository/raw/macosx-wine-development/$VERSION$RELEASE-x86"
./server/publish.py "$repo_path" repository/winehq/macosx/i686

for codename in stretch wheezy jessie sid; do
	for arch in x86 x64; do

		repo_path="repository/raw/debian-$codename-development/$VERSION$RELEASE-$arch"
		./server/publish.py "$repo_path" repository/winehq/debian

	done
done

for codename in 5 4; do
	for arch in x86 x64; do

		repo_path="repository/raw/mageia-$codename-development/$VERSION$RELEASE-$arch"
		./server/publish.py "$repo_path" "repository/winehq/mageia/$codename"

	done
done

for codename in 22 23; do
	for arch in x86 x64; do

		repo_path="repository/raw/fedora-$codename-development/$VERSION$RELEASE-$arch"
		./server/publish.py "$repo_path" "repository/winehq/fedora/$codename"

	done
done
