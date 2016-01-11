#!/bin/bash
#
# Script to push changes to launchpad
#
# Copyright (C) 2015 Michael Müller
# Copyright (C) 2015-2016 Sebastian Lackner
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

update_bzr()
{
	bzrurl="$1"
	distro="$2"

	if [ ! -d "temp/$distro/debian" ]; then
		echo "ERROR: No packaging files found for $distro, run packaging/generate.py first." >&2
		exit 1
	fi

	# Checkout repository
	mkdir -p launchpad
	rm -rf "launchpad/$distro"
	bzr checkout --lightweight "$bzrurl" "launchpad/$distro"

	# Update debian/ directory
	rm -rf "launchpad/$distro/debian"
	cp -r "temp/$distro/debian" "launchpad/$distro"

	# Compute diff
	tmpfile=$(mktemp)
	(cd "launchpad/$distro"; bzr diff || true) > "$tmpfile"

	# Empty diff -> nothing to commit
	if [ ! -s "$tmpfile" ]; then
		echo "Nothing to commit for $distro"
		rm "$tmpfile"
		return 0
	fi

	# Only timestamp changed -> nothing to commit
	if ! cat "$tmpfile" | filterdiff -x debian/changelog | grep "^+++" &> /dev/null; then
		if ! cat "$tmpfile" | grep -v "\(^--- \|^+++ \)" |
			 grep -v "^[+-] -- .* <[^>]\+>  .*" | grep "^[+-]"; then
			echo "Nothing to commit for $distro"
			rm "$tmpfile"
			return 0
		fi
	fi

	echo "###################################"
	echo ""
	cat "$tmpfile" | colordiff
	echo "###################################"
	echo ""

	# Read commit message and commit changes
	version=$(head -n1 "launchpad/$distro/debian/changelog" | sed -e 's/.*(\(.*\)).*/\1/')
	read -e -p "Commit message (CTRL-C to abort): " -i "Update to $version." commit_msg
	(cd "launchpad/$distro"; bzr add "debian" && bzr commit -m "$commit_msg")

	rm "$tmpfile"
	return 0
}

if [ ! -d "packaging" ]; then
	echo "ERROR: Called from wrong directory, aborting." >&2
	exit 1
fi

update_bzr "lp:~wine/wine/build-development" "ubuntu-any-development"
update_bzr "lp:~wine/wine/build-staging" "ubuntu-any-staging"

exit 0
