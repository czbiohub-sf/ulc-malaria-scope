help:
	@echo "lint - check code style with flake8"
	@echo "test - run tests only"
	@echo "coverage - run tests and check code coverage"
	@echo "conda_install (recommended) - Install requirements "

test:
	py.test

coverage:
	coverage run --source detection --omit="*/test*" --module py.test
	coverage report --show-missing
