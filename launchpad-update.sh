#!/bin/bash
#
# Script to push changes to launchpad
#
# Copyright (C) 2015 Michael Müller
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
set -eu

function update_bzr {
	dir="$1"
	url="$2"
	ver="$3"
	rel="$4"
	distro="$5"

	# Until someone tells me a bzr alternative for
	# git reset --hard origin; git clean -f -d
	# remove pre existing checkouts and use lightweights ones
	# (cd "$dir"; bzr revert -q; bzr uncommit -q --local --force; bzr pull --overwrite "$url")

	rm -rf "$dir"
	bzr checkout --lightweight "$url" "$dir"

	# remove debian folder
	rm -rf "$dir/debian"
	if [ -z "$rel" ]; then
		packaging/tools/generate.py --ver "$ver" --skip-name --out "$dir" "$distro"
	else
		packaging/tools/generate.py --ver "$ver" --rel "$rel" --skip-name --out "$dir" "$distro"
	fi

	changes=$(cd "$dir"; bzr diff; true)
	if [ -z "$changes" ]; then
		echo "Nothing to commit for $distro"
		return 0
	fi

	changes_without_changelog=$(echo "$changes" | filterdiff -x debian/changelog | grep -v "^=== "; true)
	if [ -z "$changes_without_changelog" ]; then

		# Only the changelog changed, check if only the timestamp changed
		lines_changed=$(cd "$dir"; bzr diff --context=0 | grep -v "\(^=== \|^--- \|^+++ \|^@@ \)" ; true)
		lines_changed=$(echo "$lines_changed" | grep -v -E '^[+|-] -- .* <[^>]+>  [A-Za-z]+, [0-9]+ [A-Za-z]+ [0-9]+ [0-9]{2}:[0-9]{2}:[0-9]{2} [+-][0-9]{4}'; true)

		if [ -z "$lines_changed" ]; then
			echo "No changes for $distro"
			return 0
		fi
	fi

	ver_str="$ver"
	if [ ! -z "$rel" ]; then
		ver_str="$ver_str-$rel"
	fi

	echo "###################################"
	echo ""
	(cd "$dir"; bzr diff | colordiff)
	echo "###################################"
	echo ""
	read -e -p "Commit message (CTRL-C to abort): " -i "Update to $ver_str" commit_msg
	(cd "$dir"; bzr add "debian"; bzr commit -m "$commit_msg")

	return 0
}

function update_all {
	ver="$1"
	rel="$2"

	if [ ! -d launchpad ]; then
		mkdir launchpad
	fi

	update_bzr launchpad/wine-build-development \
		"lp:~wine/wine/build-development" "$ver" "$rel" "ubuntu-any-development"
	update_bzr launchpad/wine-build-staging \
		"lp:~wine/wine/build-staging" "$ver" "$rel" "ubuntu-any-staging"
}

function usage {
	echo ""
	echo "Usage: launchpad-update.sh --ver VERSION [--rel REL]"
	echo ""
	echo "  --ver VERSION               update bzr branches for wine version VERSION"
	echo "  --rel REL                   update bzr branches for debian-version REL"
	echo ""
}

# Print usage message when no arguments are given at all
if [ $# -eq 0 ]; then
	usage
	exit 0
fi

ver=""
rel=""

while [[ $# > 0 ]] ; do
	CMD="$1"; shift
	case "$CMD" in
		--ver)
			ver="$1"
			shift
			;;
		--ver=*)
			ver="${CMD#*=}";
			;;

		--rel)
			rel="$1"
			shift
			;;
		--rel=*)
			rel="${CMD#*=}";
			;;

		--help)
			usage
			exit 0
			;;
		*)
			echo "ERROR: Unknown argument $CMD." >&2
			exit 1
			;;
	esac
done

if [ -z "$ver" ]; then
	usage
	exit 1
fi

update_all "$ver" "$rel"
exit 0
