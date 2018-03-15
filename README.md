# libfaketimefs

This is a FUSE filesystem that provides a dynamic `faketimerc` file for [libfaketime](https://github.com/wolfcw/libfaketime). The primary use case it to allow consistent fast forward behaviour across multiple processes. This is intended for testing environments only and should not be used in a production system.

## Usage

Install and start libfaketimefs in the foreground:

```
# Install libfaketimefs
pip install libfaketimefs

# Create a mount point
mkdir -p /run/libfaketimefs

# Run libfaketimefs using the mount point
libfaketimefs /run/libfaketimefs
```

Use libfaketime and libfaketimefs to fast forward at 60 seconds per second:

```
# Build and send a fast forward command (see the File API documentation)
NOW=$(date +%s)
TOMORROW=$(date -d tomorrow +%s)
RATE=180
echo "$NOW $NOW $TOMORROW $RATE" > /run/libfaketimefs/control

# Enable libfaketime and configure it to use libfaketimefs
export LD_PRELOAD=libfaketime.so.1
export FAKETIME_TIMESTAMP_FILE=/run/libfaketimefs/faketimerc
export FAKETIME_NO_CACHE=1

# Watch the result
watch -n 1 date
```

## File API: `/control`

This file controls the dynamic value of `faketimerc` using a specific command format.

Format:
```
REF TIME1 TIME2 RATE
```

| Parameter | Type                         | Description                                  |
| --------- | ---------------------------- | -------------------------------------------- |
| `REF`     | integer (unix timestamp)     | When the command was issued (real time)      |
| `TIME1`   | integer (unix timestamp)     | The starting fake time                       |
| `TIME2`   | integer (unix timestamp)     | The ending fake time                         |
| `RATE`    | integer (seconds per second) | The rate to move between `TIME1` and `TIME2` |
-----

When a valid command is written to `/control`, the value of `/faketimerc` will be dynamically generated to output an offset according to the command. When the fake time has reached `TIME2` then it will continue at normal speed.

To jump to a specific time, and not fast forward between two times, use the same value for `TIME1` and `TIME2`.

The fake time is calculated as though it has been fast forwarding since the `REF` time, which may or may not be the same as when the command is received. This helps when running libfaketimefs across multiple machines that may receive the command at different times. For example, one machine may boot up while other machines have been fast forwarding. Given the same command as the other machines, and synchonised system times via NTP, all machines will have the same fast forwarded fake time.

## File API: `/faketimerc`

This file contains a dynamically generated offset according to the `/control` command. If no command has been written to `/control` then it will contain `+0` which is the same as the real time. libfaketime should be configured to use this file with `FAKETIME_TIMESTAMP_FILE` and `FAKETIME_NO_CACHE` should be used to avoid libfaketime's cache behaviour.

## File API: `/realtime`

This file contains the real system time formatted as a unix timestamp floating point number. This is an escape hatch for programs under the effects of libfaketime to access the real time.

## File API: `/status`

This file contains the current status of libfaketimefs. While fast forwarding, the value is `MOVING`. Otherwise, the value is `IDLE`.
