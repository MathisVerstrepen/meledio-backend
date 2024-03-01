#!/bin/bash

SCRIPTS_DIR=$(pwd)
PROJECT_DIR="$SCRIPTS_DIR"/../..
BACCHUS_DIR="$PROJECT_DIR"/bacchus
DOCKER_DIR="$SCRIPTS_DIR"/../dev

# Export environment variables
export BACCHUS_FOLDER="$BACCHUS_DIR"/dev
export ARES_FOLDER="$PROJECT_DIR"/ares/app
export TRITON_FOLDER="$PROJECT_DIR"/triton/app
export DB_VOLUME="$PROJECT_DIR"/docker/volumes/dev/db
export DB_CONFIG="$PROJECT_DIR"/docker/conf/db/dev
export REDIS_VOLUME="$PROJECT_DIR"/docker/volumes/dev/redis

export DB_CONF="$PROJECT_DIR"/docker/conf/db/postgres.conf

# Load .env file
export $(grep -v '^#' "$DOCKER_DIR"/.env | xargs)

# Create necessary directories
mkdir -p "$BACCHUS_DIR"/dev
mkdir -p "$BACCHUS_DIR"/dev/audio
mkdir -p "$BACCHUS_DIR"/dev/audio/tmp
mkdir -p "$BACCHUS_DIR"/dev/media 
mkdir -p "$BACCHUS_DIR"/dev/chapters
mkdir -p "$BACCHUS_DIR"/dev/reports
mkdir -p "$BACCHUS_DIR"/dev/reports/wizard
mkdir -p "$PROJECT_DIR"/docker/volumes/dev/db

# Backup dev database
sudo bash "$SCRIPTS_DIR"/backup_db.sh iris_db_dev dev

# Stop dev docker compose
sudo -E docker compose -f "$DOCKER_DIR"/back_compose.yml --profile prod down --remove-orphans --volumes

# Ask if bacchus should be cleared
read -p "Do you want to clear bacchus? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    # Clear bacchus
    sudo bash "$SCRIPTS_DIR"/clear_bacchus.sh dev
fi

# Ask if db should be reset
read -p "Do you want to reset the database? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    # Reset the database
    sudo bash "$SCRIPTS_DIR"/reset_db.sh iris_db_dev dev
fi

# Ask if the ares image should be built
read -p "Do you want to build the ares image? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    # Build the image
    sudo docker build -t dune_ares:dev -f "$DOCKER_DIR"/ares_dev.dockerfile "$PROJECT_DIR"
fi

# Ask if the triton image should be built
read -p "Do you want to build the triton image? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    # Build the image
    sudo docker build -t dune_triton:dev -f "$DOCKER_DIR"/triton_dev.dockerfile "$PROJECT_DIR"
fi

# Start dev docker compose
sudo -E docker compose -f "$DOCKER_DIR"/back_compose.yml --profile prod up -d --remove-orphans --force-recreate