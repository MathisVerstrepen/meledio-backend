#!/bin/bash

SCRIPTS_DIR=$(pwd)
PROJECT_DIR="$SCRIPTS_DIR"/../..
BACCHUS_DIR="$PROJECT_DIR"/bacchus
DOCKER_DIR="$SCRIPTS_DIR"/../prod

# Export environment variables
export BACCHUS_FOLDER="$BACCHUS_DIR"/prod
export ARES_FOLDER="$PROJECT_DIR"/ares/app
export TRITON_FOLDER="$PROJECT_DIR"/triton/app
export DB_VOLUME="$PROJECT_DIR"/docker/volumes/prod/db
export DB_CONFIG="$PROJECT_DIR"/docker/conf/db/prod
export REDIS_VOLUME="$PROJECT_DIR"/docker/volumes/prod/redis

export DB_CONF="$PROJECT_DIR"/docker/conf/db/postgres.conf

# Load .env file
export $(grep -v '^#' "$DOCKER_DIR"/.env | xargs)

# Create necessary directories
mkdir -p "$BACCHUS_DIR"/prod
mkdir -p "$BACCHUS_DIR"/prod/audio
mkdir -p "$BACCHUS_DIR"/prod/audio/tmp
mkdir -p "$BACCHUS_DIR"/prod/media 
mkdir -p "$BACCHUS_DIR"/prod/chapters
mkdir -p "$BACCHUS_DIR"/prod/reports
mkdir -p "$BACCHUS_DIR"/prod/reports/wizard
mkdir -p "$PROJECT_DIR"/docker/volumes/prod/db

# Execute the backup script in sudo mode
sudo bash "$SCRIPTS_DIR"/backup_db.sh iris_db_prod prod

# Stop prod docker compose
sudo -E docker compose -f "$DOCKER_DIR"/back_compose.yml --profile prod down --remove-orphans --volumes

# Ask if bacchus should be cleared
read -p "Do you want to clear bacchus? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    # Clear bacchus
    sudo bash "$SCRIPTS_DIR"/clear_bacchus.sh prod
fi

# Ask if the ares image should be built
read -p "Do you want to build the ares image? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    # Build the image
    sudo docker build -t dune_ares:prod -f "$DOCKER_DIR"/ares_prod.dockerfile "$PROJECT_DIR"
fi

# Ask if the triton image should be built
read -p "Do you want to build the triton image? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    # Build the image
    sudo docker build -t dune_triton:prod -f "$DOCKER_DIR"/triton_prod.dockerfile "$PROJECT_DIR"
fi

# Start prod docker compose
sudo -E docker compose -f "$DOCKER_DIR"/back_compose.yml --profile prod up -d --remove-orphans --force-recreate