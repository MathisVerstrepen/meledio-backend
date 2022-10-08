CREATE SCHEMA IF NOT EXISTS iris AUTHORIZATION supabase_admin;

-- --------------------GAMES-------------------- --

CREATE TABLE iris.games (
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

ALTER TABLE iris.games ADD FOREIGN KEY ("parent_game") REFERENCES iris.games ("id");
-- ALTER TABLE "games" ADD FOREIGN KEY ("similar_games") REFERENCES "games" ("id");
-- ALTER TABLE "games" ADD FOREIGN KEY ("standalone_expansions") REFERENCES "games" ("id");

-- --------------------DLCS-------------------- --

CREATE TABLE iris.dlcs (
  "id" SERIAL PRIMARY KEY,
  "game_id" int,
  "dlcs_id" int
);

ALTER TABLE iris.dlcs ADD FOREIGN KEY ("game_id") REFERENCES iris.games ("id");
ALTER TABLE iris.dlcs ADD FOREIGN KEY ("dlcs_id") REFERENCES iris.games ("id");

-- --------------------EXPANDED GAMES-------------------- --

CREATE TABLE iris.expanded_games (
  "id" SERIAL PRIMARY KEY,
  "game_id" int,
  "expanded_games_id" int
);

ALTER TABLE iris.expanded_games ADD FOREIGN KEY ("game_id") REFERENCES iris.games ("id");
ALTER TABLE iris.expanded_games ADD FOREIGN KEY ("expanded_games_id") REFERENCES iris.games ("id");

-- --------------------EXPANSIONS-------------------- --

CREATE TABLE iris.expansions (
  "id" SERIAL PRIMARY KEY,
  "game_id" int,
  "expansions_id" int
);

ALTER TABLE iris.expansions ADD FOREIGN KEY ("game_id") REFERENCES iris.games ("id");
ALTER TABLE iris.expansions ADD FOREIGN KEY ("expansions_id") REFERENCES iris.games ("id");

-- --------------------SIMILAR GAMES-------------------- --

CREATE TABLE iris.similar_games (
  "id" SERIAL PRIMARY KEY,
  "game_id" int,
  "similar_games_id" int
);

ALTER TABLE iris.similar_games ADD FOREIGN KEY ("game_id") REFERENCES iris.games ("id");
ALTER TABLE iris.similar_games ADD FOREIGN KEY ("similar_games_id") REFERENCES iris.games ("id");

-- --------------------STANDALONE EXPANSIONS-------------------- --

CREATE TABLE iris.standalone_expansions (
  "id" SERIAL PRIMARY KEY,
  "game_id" int,
  "standalone_expansions_id" int
);

ALTER TABLE iris.standalone_expansions ADD FOREIGN KEY ("game_id") REFERENCES iris.games ("id");
ALTER TABLE iris.standalone_expansions ADD FOREIGN KEY ("standalone_expansions_id") REFERENCES iris.games ("id");

-- --------------------ALTERNATIVE NAMES-------------------- --

CREATE TABLE iris.alternative_names (
  "id" int PRIMARY KEY,
  "game_id" int,
  "comment" text,
  "name" text
);

ALTER TABLE iris.alternative_names ADD FOREIGN KEY ("game_id") REFERENCES iris.games ("id");

-- --------------------ALBUMS-------------------- --

CREATE TABLE iris.albums (
  "id" SERIAL PRIMARY KEY,
  "game_id" int,
  "file" text,
  "title" text
);

ALTER TABLE iris.albums ADD FOREIGN KEY ("game_id") REFERENCES iris.games ("id");

-- --------------------ARTWORKS-------------------- --

CREATE TABLE iris.artworks (
  "id" int PRIMARY KEY,
  "game_id" int,
  "alpha_channel" boolean DEFAULT 'false',
  "animated" boolean DEFAULT 'false',
  "height" int,
  "width" int,
  "image_id" text
);

ALTER TABLE iris.artworks ADD FOREIGN KEY ("game_id") REFERENCES iris.games ("id");

-- --------------------CATEGORY-------------------- --

CREATE TABLE iris.category (
  "id" int PRIMARY KEY,
  "name" text
);

ALTER TABLE iris.games ADD FOREIGN KEY ("category") REFERENCES iris.category ("id");

-- --------------------COLLECTION-------------------- --

CREATE TABLE iris.collection (
  "id" int PRIMARY KEY,
  "name" text,
  "slug" text
);

ALTER TABLE iris.games ADD FOREIGN KEY ("collection") REFERENCES iris.collection ("id");

-- --------------------COVER-------------------- --

CREATE TABLE iris.cover (
  "id" int PRIMARY KEY,
  "game_id" int,
  "alpha_channel" boolean DEFAULT 'false',
  "animated" boolean DEFAULT 'false',
  "height" int,
  "width" int,
  "image_id" text
);

ALTER TABLE iris.cover ADD FOREIGN KEY ("game_id") REFERENCES iris.games ("id");
-- ALTER TABLE "games" ADD FOREIGN KEY ("cover") REFERENCES "cover" ("id");

-- --------------------FRANCHISE-------------------- --

-- CREATE TABLE "franchise" (
--   "id" int PRIMARY KEY,
--   "name" text,
--   "slug" text
-- );

-- ALTER TABLE "games" ADD FOREIGN KEY ("franchise") REFERENCES "franchise" ("id");

-- --------------------GENRES-------------------- --

CREATE TABLE iris.genres (
  "id" int PRIMARY KEY,
  "game_id" int,
  "name" text,
  "slug" text
);

ALTER TABLE iris.genres ADD FOREIGN KEY ("game_id") REFERENCES iris.games ("id");

-- --------------------INVOLVED COMPANIES-------------------- --

CREATE TABLE iris.involved_companies (
  "id" int PRIMARY KEY,
  "game_id" int,
  "company" int,
  "developer" boolean,
  "porting" boolean,
  "publisher" boolean,
  "supporting" boolean
);

ALTER TABLE iris.involved_companies ADD FOREIGN KEY ("game_id") REFERENCES iris.games ("id");

-- --------------------COMPANIES-------------------- --

CREATE TABLE iris.companies (
  "id" int PRIMARY KEY,
  "description" text,
  "logo" text,
  "name" text,
  "slug" text
);

ALTER TABLE iris.involved_companies ADD FOREIGN KEY ("company") REFERENCES iris.companies ("id");
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

CREATE TABLE iris.keywords (
  "id" int PRIMARY KEY,
  "game_id" int,
  "name" text,
  "slug" text
);

ALTER TABLE iris.keywords ADD FOREIGN KEY ("game_id") REFERENCES iris.games ("id");

-- --------------------SCREENSHOTS-------------------- --

CREATE TABLE iris.screenshots (
  "id" int PRIMARY KEY,
  "game_id" int,
  "alpha_channel" boolean DEFAULT 'false',
  "animated" boolean DEFAULT 'false',
  "height" int,
  "width" int,
  "image_id" text
);

ALTER TABLE iris.screenshots ADD FOREIGN KEY ("game_id") REFERENCES iris.games ("id");

-- --------------------THEMES-------------------- --

CREATE TABLE iris.themes (
  "id" int PRIMARY KEY,
  "game_id" int,
  "name" text,
  "slug" text
);

ALTER TABLE iris.themes ADD FOREIGN KEY ("game_id") REFERENCES iris.games ("id");

-- --------------------POPULATE CATEGORY-------------------- --

INSERT INTO iris.category (id, name) VALUES 
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