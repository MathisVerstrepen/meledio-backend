CREATE SCHEMA IF NOT EXISTS iris AUTHORIZATION supabase_admin;

-- --------------------collection-------------------- --

CREATE TABLE iris.collection (
  "id" int PRIMARY KEY,
  "name" text,
  "slug" text
);

-- --------------------game-------------------- --

CREATE TABLE iris.game (
  "id" int PRIMARY KEY,
  "name" text,
  "slug" text,
  "complete" boolean,
  "parent_game" int,
  "category" int,
  "collection_id" int,
  "first_release_date" date,
  "rating" double precision,
  "popularity" int,
  "summary" text,
);

ALTER TABLE "game" ADD FOREIGN KEY ("collection_id") REFERENCES "collection" ("id");
ALTER TABLE "game" ADD FOREIGN KEY ("parent_game") REFERENCES "game" ("id");

-- ----------extra_content(DLCS, EXPANDED GAMES, EXPANSIONS, SIMILAR GAMES, STANDALONE EXPANSIONS)---------- --

CREATE TABLE iris.extra_content (
  "game_id" int NOT NULL,
  "extra_id" int NOT NULL,
  "type" text,

  PRIMARY KEY ("game_id", "extra_id")
);

ALTER TABLE "extra_content" ADD FOREIGN KEY ("game_id") REFERENCES "game" ("id");
ALTER TABLE "extra_content" ADD FOREIGN KEY ("extra_id") REFERENCES "game" ("id");

-- --------------------alternative name-------------------- --

CREATE TABLE iris.alternative_name (
  "id" int PRIMARY KEY,
  "game_id" int,
  "name" text,
  "comment" text
);

ALTER TABLE "alternative_name" ADD FOREIGN KEY ("game_id") REFERENCES "game" ("id");

-- --------------------album-------------------- --

CREATE TABLE iris.album (
  "id" SERIAL PRIMARY KEY,
  "game_id" int,
  "name" text,
  "slug" text,
  "folder" int,
  "n_track" int
);

ALTER TABLE "album" ADD FOREIGN KEY ("game_id") REFERENCES "game" ("id");

-- --------------------track-------------------- --

CREATE TABLE iris.track (
  "id" SERIAL PRIMARY KEY,
  "game_id" int,
  "title" text,
  "slug" text,
  "file" text,
  "view_count" int,
  "like_count" int,
  "length" int,
);

ALTER TABLE "track" ADD FOREIGN KEY ("game_id") REFERENCES "game" ("id");

-- --------------------playlist-------------------- --

CREATE TABLE iris.playlist (
  "id" SERIAL PRIMARY KEY,
  "name" text,
  "tracklist" text[],
  "cover" text,
  "created_at" date,
  "updated_at" date,
  "created_by" int,
  "public" boolean,
);

ALTER TABLE "playlist" ADD FOREIGN KEY ("tracklist") REFERENCES "game" ("id");

-- --------------------media-------------------- --

CREATE TABLE iris.media (
  "image_id" text,
  "game_id" text,
  "type" text,
  "height" int,
  "width" int
);

ALTER TABLE "media" ADD FOREIGN KEY ("game_id") REFERENCES "game" ("id");

-- --------------------genre-------------------- --

CREATE TABLE iris.genre (
  "game_id" int,
  "name" text,
  "slug" text
);

ALTER TABLE "genre" ADD FOREIGN KEY ("game_id") REFERENCES "game" ("id");

-- --------------------company-------------------- --

CREATE TABLE iris.company (
  "id" int PRIMARY KEY,
  "name" text,
  "slug" text
  "description" text,
  "logo_id" text,
);

-- --------------------involved companies-------------------- --

CREATE TABLE iris.involved_companies (
  "game_id" int,
  "company_id" int,
  "developer" boolean,
  "porting" boolean,
  "publisher" boolean,
  "supporting" boolean
);

ALTER TABLE "involved_companies" ADD FOREIGN KEY ("game_id") REFERENCES "game" ("id");
ALTER TABLE "involved_companies" ADD FOREIGN KEY ("company_id") REFERENCES "company" ("id");

-- --------------------keyword-------------------- --

CREATE TABLE iris.keyword (
  "id" int PRIMARY KEY,
  "game_id" int,
  "name" text,
  "slug" text
);

ALTER TABLE "keyword" ADD FOREIGN KEY ("game_id") REFERENCES "game" ("id");

-- --------------------theme-------------------- --

CREATE TABLE iris.themes (
  "game_id" int,
  "name" text,
  "slug" text
);

ALTER TABLE "theme" ADD FOREIGN KEY ("game_id") REFERENCES "game" ("id");




-- --------------------POPULATE CATEGORY-------------------- --

-- INSERT INTO iris.category (id, name) VALUES 
--   (0, 'main_game'),
--   (1, 'dlc_addon'),
--   (2, 'expansion'),
--   (3, 'bundle'),
--   (4, 'standalone_expansion'),
--   (5, 'mod'),
--   (6, 'episode'),
--   (7, 'season'),
--   (8, 'remake'),
--   (9, 'remaster'),
--   (10, 'expanded_game'),
--   (11, 'port'),
--   (12, 'fork');