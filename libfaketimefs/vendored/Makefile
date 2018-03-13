all: fusepy

fusepy:
	git clone --branch v2.0.4 --depth 1 https://github.com/fusepy/fusepy.git
	rm -rf fusepy/.git
	touch fusepy/__init__.py

clean:
	rm -rf fusepy
