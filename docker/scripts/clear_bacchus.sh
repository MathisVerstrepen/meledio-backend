#!/bin/bash

db_type=$1

SCRIPTS_DIR=$(pwd)
PROJECT_DIR="$SCRIPTS_DIR"/../..
BACCHUS_DIR="$PROJECT_DIR"/bacchus

# Supprimer les fichiers audio
rm -rf -- "$BACCHUS_DIR"/$db_type/audio/*
mkdir "$BACCHUS_DIR"/$db_type/audio/tmp

# Supprimer les fichiers images
rm -rf -- "$BACCHUS_DIR"/$db_type/media/*

# Supprimer les fichiers de chapitres
rm -rf -- "$BACCHUS_DIR"/$db_type/chapters/*

# Supprime les fichiers de rapports
rm -rf -- "$BACCHUS_DIR"/$db_type/reports/*
mkdir "$BACCHUS_DIR"/$db_type/reports/wizard