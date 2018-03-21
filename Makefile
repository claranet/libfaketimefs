# http://clarkgrubb.com/makefile-style-guide

MAKEFLAGS += --warn-undefined-variables --no-print-directory
SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := test
.DELETE_ON_ERROR:
.SUFFIXES:

################
# Python build #
################

$(eval NAME := $(shell python setup.py --name))
$(eval PY_NAME := $(shell python setup.py --name | sed 's/-/_/g'))
$(eval VERSION := $(shell python setup.py --version))

SOURCE := $(shell find bin libfaketimefs -type f) setup.py
SDIST := dist/$(NAME)-$(VERSION).tar.gz
WHEEL := dist/$(PY_NAME)-$(VERSION)-py2.py3-none-any.whl

$(SDIST): $(SOURCE)
	python setup.py sdist

$(WHEEL): $(SOURCE)
	python setup.py bdist_wheel

.PHONY: test
test:
	python -m doctest libfaketimefs_ctl/__init__.py
	flake8 bin/libfaketimefs libfaketimefs/__init__.py setup.py

.PHONY: build
build: $(SDIST) $(WHEEL)

.PHONY: upload
upload: $(SDIST) $(WHEEL)
	twine upload $(SDIST) $(WHEEL)

.PHONY: clean
clean:
	rm -rf build dist *.egg-info testmount

#################
# Local testing #
#################

# Run libfaketimefs.
.PHONY: run
run:
	flake8 ./bin/* ./libfaketimefs/*.py || true
	mkdir -p testmount
	libfaketimefs testmount --debug

now := $(shell date +%s)
now10s := $(shell date -d '+10 seconds' +%s)
now10m := $(shell date -d '+10 minutes' +%s)
tomorrow := $(shell date -d '+86400 seconds' +%s)
tomorrow10s := $(shell date -d '+86410 seconds' +%s)

# Jump to now.
.PHONY: jump
jump:
	echo '$(now) $(now) $(now) 1' > testmount/control
	watch -n 1 "cat testmount/realtime && echo && cat testmount/faketimerc"

# Jump to tomorrow.
.PHONY: jump1d
jump1d:
	echo '$(now) $(tomorrow) $(tomorrow) 1' > testmount/control
	watch -n 1 "cat testmount/realtime && echo && cat testmount/faketimerc"

# Move at normal speed. This is useless.
.PHONY: move1s
move1s:
	echo '$(now) $(now) $(now10s) 1' > testmount/control
	watch -n 1 "cat testmount/realtime && echo && cat testmount/faketimerc"

# Move at double speed.
.PHONY: move2s
move2s:
	echo '$(now) $(now) $(now10s) 2' > testmount/control
	watch -n 1 "cat testmount/realtime && echo && cat testmount/faketimerc"

# Move at double speed starting tomorrow.
.PHONY: move2st
move2st:
	echo '$(now) $(tomorrow) $(tomorrow10s) 2' > testmount/control
	watch -n 1 "cat testmount/realtime && echo && cat testmount/faketimerc"

# Move at 1 minute per second.
.PHONY: move1m
move1m:
	echo '$(now) $(now) $(now10m) 60' > testmount/control
	watch -n 1 "cat testmount/realtime && echo && cat testmount/faketimerc"

# Move at 24 minutes per second, or 1 day per minute.
.PHONY: move24m
move24m:
	echo '$(now) $(now) $(tomorrow) 1440' > testmount/control
	watch -n 1 "cat testmount/realtime && echo && cat testmount/faketimerc"
