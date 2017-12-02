PROJECT_NAME=pymymusic
APP_ENTRY_POINT=src/main.py
DOCKER_PROJECT_NAME=pymymusic
TEST_PATH=tests
export CONFIG_FILENAME := config_dev.ini

test: clean-pyc clean-build
	pytest --verbose --color=yes $(TEST_PATH)


clean-pyc:
	find . -name '*.pyc' -exec rm --force {} +
	find . -name '*.pyo' -exec rm --force {} +
	find . -name '*~' -exec rm --force  {} +

clean-build:
	rm --force --recursive build/
	rm --force --recursive dist/
	rm --force --recursive *.egg-info

isort:
	sh -c "isort --skip-glob=.tox --recursive . "

lint:
	flake8 --exclude=.tox

run:
	python $(APP_ENTRY_POINT)


run-with-args:
	@read -p "Enter arguments to run: " arguments; \
	python $(APP_ENTRY_POINT) $$arguments

docker-compose-build:
	docker-compose build $(DOCKER_PROJECT_NAME)

docker-compose-run-app:
	docker-compose run $(DOCKER_PROJECT_NAME)

docker-compose-up:
	docker-compose up

docker-run:
	docker build --file=./Dockerfile --tag=$(DOCKER_PROJECT_NAME) ./
	docker run --detach=false --name=$(DOCKER_PROJECT_NAME)) $(DOCKER_PROJECT_NAME)
