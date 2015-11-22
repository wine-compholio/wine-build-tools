#!/bin/bash
#
# Wrapper script to start build process inside of a VM.
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

LOG_TTY="/dev/ttyS1"
BUILD_USER="builder"
BUILD_GROUP="builder"

# Do not attempt to build twice.
if [ -f /build/status ]; then
    echo "ERROR: Build already done, ignoring." >&2
    exit 1
fi

# Make sure that this script was executed properly.
if [ ! -d /build ]; then
    echo "ERROR: Build directory doesn't exist." >&2
    exit 1
fi

echo 100    > /build/status
echo -n ""  > /build/log

# Set the language
export LANG=en_US.utf8
(echo ""; echo "export LANG=en_US.utf8") >> /etc/profile

# Execute the main script
if [ -e "$LOG_TTY" ]; then
    if [ -x /build/source/boot.sh ]; then

        # Wait for network to come up
        if command -v wget >/dev/null 2>&1; then
            print_once=0
            while ! wget -q --timeout=20 --spider http://google.com; do
                if [ "$print_once" -eq 0 ]; then
                    (
                        echo " *** WAITING FOR DHCP SERVER ***"
                        echo ""
                    ) | tee -a /build/log > "$LOG_TTY"
                    print_once=1
                fi
                sleep 10
            done
        fi

        # Run the boot.sh script
        (
            chown "root:$BUILD_GROUP" /build
            chmod g+w /build
            chown -R "$BUILD_USER:$BUILD_GROUP" /build/source
            chmod -R g+w /build/source
            cd /build/source && ./boot.sh
        )  2>&1 | tee -a /build/log > "$LOG_TTY"
        status="${PIPESTATUS[0]}"
        if [ "$status" -ne 0 ]; then
            (
                echo ""
                echo " *** BUILD FAILED WITH EXITCODE $status ***"
            ) | tee -a /build/log > "$LOG_TTY"
        fi
        echo "$status" > /build/status

    fi
fi

shutdown -hP now
exit "$status"
