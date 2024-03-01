#!/bin/bash

SCRIPTS_DIR=$(pwd)

container_name=$1
db_type=$2

# Vérifie si le nom du conteneur et le type de base de données ont été fournis
if [ -z "$container_name" ] || [ -z "$db_type" ]
then
    echo "Le nom du conteneur et le type de base de données doivent être fournis."
    exit 1
fi

# Arrête le conteneur Docker PostgreSQL
docker stop $container_name

# Supprime le dossier associé à la base de données
rm -rf "$SCRIPTS_DIR"/../volumes/$db_type/db

echo "La base de données a été réinitialisée avec succès."
