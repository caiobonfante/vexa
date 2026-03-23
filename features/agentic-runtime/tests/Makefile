include ../.env

.PHONY: infra-up infra-down test test-mvp0 build clean

build:
	cd ../../.. && docker build -t vexa-agent:dev -f containers/agent/Dockerfile .
	cd ../../.. && docker build -t vexa-chat-api:dev -f services/chat-api/Dockerfile .

infra-up:
	docker compose -f ../deploy/docker-compose.yml --env-file ../.env up -d

infra-down:
	docker compose -f ../deploy/docker-compose.yml --env-file ../.env down

test: test-mvp0 test-mvp05

test-mvp0:
	bash test-mvp0.sh http://localhost:$(CHAT_API_PORT)

test-mvp05:
	bash test-mvp05.sh http://localhost:$(CHAT_API_PORT)

clean:
	docker ps -a --filter label=vexa.managed=true -q | xargs -r docker rm -f
