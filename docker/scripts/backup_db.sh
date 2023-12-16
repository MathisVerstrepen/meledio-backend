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

# Définit le répertoire de sauvegarde
backup_dir="$SCRIPTS_DIR"/../backups/$db_type

# Crée le répertoire de sauvegarde
mkdir -p $backup_dir

# Nom de fichier de sauvegarde avec la date et l'heure
backup_file="db_backup_$(date +%Y-%m-%d_%H-%M-%S).sql"

# Effectue une sauvegarde de la base de données dans le répertoire temporaire
docker exec $container_name pg_dumpall -U postgres > $backup_dir/$backup_file

# Arrête le conteneur Docker PostgreSQL
docker stop $container_name

# Supprime le dossier associé à la base de données
rm -rf "$SCRIPTS_DIR"/../volumes/$db_type/db

echo "La sauvegarde de la base de données a été effectuée avec succès."
