CREATE DATABASE "iris_db";

-- --------------------GAMES-------------------- --

CREATE TABLE "games" (
  "id" int PRIMARY KEY,
  "category" int,
  "collection" int,
  "complete" boolean,
  -- "cover" int,
  "first_release_date" date,
  -- "franchise" int,
  "name" text,
  "parent_game" int,
  "rating" double precision,
  -- "similar_games" int,
  "slug" text,
  -- "standalone_expansions" int,
  "summary" text
);

ALTER TABLE "games" ADD FOREIGN KEY ("parent_game") REFERENCES "games" ("id");
-- ALTER TABLE "games" ADD FOREIGN KEY ("similar_games") REFERENCES "games" ("id");
-- ALTER TABLE "games" ADD FOREIGN KEY ("standalone_expansions") REFERENCES "games" ("id");

-- --------------------DLCS-------------------- --

CREATE TABLE "dlcs" (
  "id" SERIAL PRIMARY KEY,
  "game_id" int,
  "dlcs_id" int
);

ALTER TABLE "dlcs" ADD FOREIGN KEY ("game_id") REFERENCES "games" ("id");
ALTER TABLE "dlcs" ADD FOREIGN KEY ("dlcs_id") REFERENCES "games" ("id");

-- --------------------EXPANDED GAMES-------------------- --

CREATE TABLE "expanded_games" (
  "id" SERIAL PRIMARY KEY,
  "game_id" int,
  "expanded_games_id" int
);

ALTER TABLE "expanded_games" ADD FOREIGN KEY ("game_id") REFERENCES "games" ("id");
ALTER TABLE "expanded_games" ADD FOREIGN KEY ("expanded_games_id") REFERENCES "games" ("id");

-- --------------------EXPANSIONS-------------------- --

CREATE TABLE "expansions" (
  "id" SERIAL PRIMARY KEY,
  "game_id" int,
  "expansions_id" int
);

ALTER TABLE "expansions" ADD FOREIGN KEY ("game_id") REFERENCES "games" ("id");
ALTER TABLE "expansions" ADD FOREIGN KEY ("expansions_id") REFERENCES "games" ("id");

-- --------------------SIMILAR GAMES-------------------- --

CREATE TABLE "similar_games" (
  "id" SERIAL PRIMARY KEY,
  "game_id" int,
  "similar_games_id" int
);

ALTER TABLE "similar_games" ADD FOREIGN KEY ("game_id") REFERENCES "games" ("id");
ALTER TABLE "similar_games" ADD FOREIGN KEY ("similar_games_id") REFERENCES "games" ("id");

-- --------------------STANDALONE EXPANSIONS-------------------- --

CREATE TABLE "standalone_expansions" (
  "id" SERIAL PRIMARY KEY,
  "game_id" int,
  "standalone_expansions_id" int
);

ALTER TABLE "standalone_expansions" ADD FOREIGN KEY ("game_id") REFERENCES "games" ("id");
ALTER TABLE "standalone_expansions" ADD FOREIGN KEY ("standalone_expansions_id") REFERENCES "games" ("id");

-- --------------------ALTERNATIVE NAMES-------------------- --

CREATE TABLE "alternative_names" (
  "id" int PRIMARY KEY,
  "game_id" int,
  "comment" text,
  "name" text
);

ALTER TABLE "alternative_names" ADD FOREIGN KEY ("game_id") REFERENCES "games" ("id");

-- --------------------ALBUMS-------------------- --

CREATE TABLE "albums" (
  "id" SERIAL PRIMARY KEY,
  "game_id" int,
  "file" text,
  "title" text
);

ALTER TABLE "albums" ADD FOREIGN KEY ("game_id") REFERENCES "games" ("id");

-- --------------------ARTWORKS-------------------- --

CREATE TABLE "artworks" (
  "id" int PRIMARY KEY,
  "game_id" int,
  "alpha_channel" boolean DEFAULT 'false',
  "animated" boolean DEFAULT 'false',
  "height" int,
  "width" int,
  "image_id" text
);

ALTER TABLE "artworks" ADD FOREIGN KEY ("game_id") REFERENCES "games" ("id");

-- --------------------CATEGORY-------------------- --

CREATE TABLE "category" (
  "id" int PRIMARY KEY,
  "name" text
);

ALTER TABLE "games" ADD FOREIGN KEY ("category") REFERENCES "category" ("id");

-- --------------------COLLECTION-------------------- --

CREATE TABLE "collection" (
  "id" int PRIMARY KEY,
  "name" text,
  "slug" text
);

ALTER TABLE "games" ADD FOREIGN KEY ("collection") REFERENCES "collection" ("id");

-- --------------------COVER-------------------- --

CREATE TABLE "cover" (
  "id" int PRIMARY KEY,
  "game_id" int,
  "alpha_channel" boolean DEFAULT 'false',
  "animated" boolean DEFAULT 'false',
  "height" int,
  "width" int,
  "image_id" text
);

ALTER TABLE "cover" ADD FOREIGN KEY ("game_id") REFERENCES "games" ("id");
-- ALTER TABLE "games" ADD FOREIGN KEY ("cover") REFERENCES "cover" ("id");

-- --------------------FRANCHISE-------------------- --

-- CREATE TABLE "franchise" (
--   "id" int PRIMARY KEY,
--   "name" text,
--   "slug" text
-- );

-- ALTER TABLE "games" ADD FOREIGN KEY ("franchise") REFERENCES "franchise" ("id");

-- --------------------GENRES-------------------- --

CREATE TABLE "genres" (
  "id" int PRIMARY KEY,
  "game_id" int,
  "name" text,
  "slug" text
);

ALTER TABLE "genres" ADD FOREIGN KEY ("game_id") REFERENCES "games" ("id");

-- --------------------INVOLVED COMPANIES-------------------- --

CREATE TABLE "involved_companies" (
  "id" int PRIMARY KEY,
  "game_id" int,
  "company" int,
  "developer" boolean,
  "porting" boolean,
  "publisher" boolean,
  "supporting" boolean
);

ALTER TABLE "involved_companies" ADD FOREIGN KEY ("game_id") REFERENCES "games" ("id");

-- --------------------COMPANIES-------------------- --

CREATE TABLE "companies" (
  "id" int PRIMARY KEY,
  "description" text,
  "logo" text,
  "name" text,
  "slug" text
);

ALTER TABLE "involved_companies" ADD FOREIGN KEY ("company") REFERENCES "companies" ("id");
-- ALTER TABLE "companies" ADD FOREIGN KEY ("parent") REFERENCES "companies" ("id");

-- -- --------------------LOGO-------------------- --

-- CREATE TABLE "logo" (
--   "id" int PRIMARY KEY,
--   "alpha_channel" boolean,
--   "animated" boolean,
--   "height" int,
--   "width" int,
--   "image_id" text
-- );

-- ALTER TABLE "companies" ADD FOREIGN KEY ("logo") REFERENCES "logo" ("id");

-- --------------------KEYWORDS-------------------- --

CREATE TABLE "keywords" (
  "id" int PRIMARY KEY,
  "game_id" int,
  "name" text,
  "slug" text
);

ALTER TABLE "keywords" ADD FOREIGN KEY ("game_id") REFERENCES "games" ("id");

-- --------------------SCREENSHOTS-------------------- --

CREATE TABLE "screenshots" (
  "id" int PRIMARY KEY,
  "game_id" int,
  "alpha_channel" boolean DEFAULT 'false',
  "animated" boolean DEFAULT 'false',
  "height" int,
  "width" int,
  "image_id" text
);

ALTER TABLE "screenshots" ADD FOREIGN KEY ("game_id") REFERENCES "games" ("id");

-- --------------------THEMES-------------------- --

CREATE TABLE "themes" (
  "id" int PRIMARY KEY,
  "game_id" int,
  "name" text,
  "slug" text
);

ALTER TABLE "themes" ADD FOREIGN KEY ("game_id") REFERENCES "games" ("id");

-- --------------------POPULATE CATEGORY-------------------- --

INSERT INTO category (id, name) VALUES 
  (0, 'main_game'),
  (1, 'dlc_addon'),
  (2, 'expansion'),
  (3, 'bundle'),
  (4, 'standalone_expansion'),
  (5, 'mod'),
  (6, 'episode'),
  (7, 'season'),
  (8, 'remake'),
  (9, 'remaster'),
  (10, 'expanded_game'),
  (11, 'port'),
  (12, 'fork');