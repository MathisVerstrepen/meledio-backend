CREATE SCHEMA IF NOT EXISTS iris AUTHORIZATION supabase_admin;
GRANT USAGE ON SCHEMA iris TO postgres;

-- --------------------collection-------------------- --

CREATE TABLE iris.collection (
    "id" SERIAL PRIMARY KEY,
    "name" text,
    "slug" text
);

-- --------------------category-------------------- --

CREATE TABLE iris.category (
    "id" SERIAL PRIMARY KEY,
    "name" text
);

-- --------------------game-------------------- --

CREATE TABLE iris.game (
    "id" SERIAL PRIMARY KEY,
    "name" text,
    "slug" text,
    "complete" boolean,
    "parent_game" int,
    "category" int,
    "collection_id" int,
    "first_release_date" date,
    "rating" double precision,
    "popularity" int,
    "summary" text
);

ALTER TABLE iris.game ADD FOREIGN KEY ("parent_game") REFERENCES iris.game ("id");
ALTER TABLE iris.game ADD FOREIGN KEY ("collection_id") REFERENCES iris.collection ("id");
ALTER TABLE iris.game ADD FOREIGN KEY ("category") REFERENCES iris.category ("id");

-- ----------extra_content(DLCS, EXPANDED GAMES, EXPANSIONS, SIMILAR GAMES, STANDALONE EXPANSIONS)---------- --

CREATE TABLE iris.extra_content (
    "game_id" int NOT NULL,
    "extra_id" int NOT NULL,
    "type" text,

    PRIMARY KEY ("game_id", "extra_id")
);

ALTER TABLE iris.extra_content ADD FOREIGN KEY ("game_id") REFERENCES iris.game ("id");
ALTER TABLE iris.extra_content ADD FOREIGN KEY ("extra_id") REFERENCES iris.game ("id");

-- --------------------alternative name-------------------- --

CREATE TABLE iris.alternative_name (
    "id" SERIAL PRIMARY KEY,
    "game_id" int,
    "name" text,
    "comment" text
);

ALTER TABLE iris.alternative_name ADD FOREIGN KEY ("game_id") REFERENCES iris.game ("id");

-- --------------------track-------------------- --

CREATE TABLE iris.track (
    "id" SERIAL PRIMARY KEY,
    "game_id" int,
    "title" text,
    "slug" text,
    "file" uuid,
    "view_count" int,
    "like_count" int,
    "length" int
);

ALTER TABLE iris.track ADD FOREIGN KEY ("game_id") REFERENCES iris.game ("id");

-- --------------------album-------------------- --

CREATE TABLE iris.album (
    "id" SERIAL PRIMARY KEY,
    "game_id" int,
    "name" text,
    "slug" text,
    "is_ready" boolean DEFAULT false,
    "is_main" boolean DEFAULT false
);

ALTER TABLE iris.album ADD FOREIGN KEY ("game_id") REFERENCES iris.game ("id");

-- --------------------album<->track-------------------- --


CREATE TABLE iris.album_track (
    "album_id" int,
    "track_id" int,

    PRIMARY KEY ("album_id", "track_id")
);

-- --------------------playlist-------------------- --

CREATE TABLE iris.playlist (
    "id" SERIAL PRIMARY KEY,
    "name" text,
    "track_id" int,
    "cover" text,
    "created_at" date,
    "updated_at" date,
    "created_by" int,
    "public" boolean
);

ALTER TABLE iris.playlist ADD FOREIGN KEY ("track_id") REFERENCES iris.track ("id");

-- --------------------media-------------------- --

CREATE TABLE iris.media (
    "image_id" text,
    "game_id" int,
    "type" text,
    "height" int,
    "width" int
);

ALTER TABLE iris.media ADD FOREIGN KEY ("game_id") REFERENCES iris.game ("id");

-- --------------------genre-------------------- --

CREATE TABLE iris.genre (
    "game_id" int,
    "name" text,
    "slug" text
);

ALTER TABLE iris.genre ADD FOREIGN KEY ("game_id") REFERENCES iris.game ("id");

-- --------------------company-------------------- --

CREATE TABLE iris.company (
    "id" SERIAL PRIMARY KEY,
    "name" text,
    "slug" text,
    "description" text,
    "logo_id" text
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

ALTER TABLE iris.involved_companies ADD FOREIGN KEY ("game_id") REFERENCES iris.game ("id");
ALTER TABLE iris.involved_companies ADD FOREIGN KEY ("company_id") REFERENCES iris.company ("id");

-- --------------------keyword-------------------- --

CREATE TABLE iris.keyword (
    "id" SERIAL PRIMARY KEY,
    "game_id" int,
    "name" text,
    "slug" text
);

ALTER TABLE iris.keyword ADD FOREIGN KEY ("game_id") REFERENCES iris.game ("id");

-- --------------------theme-------------------- --

CREATE TABLE iris.theme (
    "game_id" int,
    "name" text,
    "slug" text
);

ALTER TABLE iris.theme ADD FOREIGN KEY ("game_id") REFERENCES iris.game ("id");

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


-- --------------------Function / Triggers-------------------- --

/*
    Delete all the tracks of an album when the album is deleted if the album is the only album of the track
*/

CREATE OR REPLACE FUNCTION delete_album_track() RETURNS trigger AS $$
BEGIN
    DELETE FROM iris.track
    WHERE id IN (
        SELECT track_id
        FROM iris.album_track
        WHERE album_id = OLD.id
    )
    AND id NOT IN (
        SELECT track_id
        FROM iris.album_track
        WHERE album_id != OLD.id
    );
    DELETE FROM iris.album_track
    WHERE album_id = OLD.id;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER delete_album_track
AFTER DELETE ON iris.album
FOR EACH ROW
EXECUTE PROCEDURE delete_album_track();

/*
    When a new album is created, check if the album already exists and if it does, delete it
*/

CREATE OR REPLACE FUNCTION check_album() RETURNS trigger AS $$
BEGIN
    IF EXISTS (
        SELECT *
        FROM iris.album
        WHERE game_id = NEW.game_id
        AND name = NEW.name
    ) THEN
        DELETE FROM iris.album
        WHERE game_id = NEW.game_id
        AND name = NEW.name;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER check_album
BEFORE INSERT ON iris.album
FOR EACH ROW
EXECUTE PROCEDURE check_album();


/*
    Create a function to get all the tracks of the main album of a game
    --> SELECT * FROM iris.get_album_tracks(%s);
*/

CREATE OR REPLACE FUNCTION iris.get_album_tracks(integer)
RETURNS TABLE (
    name text,
    slug text,
    title text,
    track_slug text,
    file uuid,
    view_count int,
    like_count int,
    length int
) AS $$
BEGIN
    RETURN QUERY SELECT a.name, a.slug, t.title, t.slug AS track_slug, t.file, t.view_count, t.like_count, t.length
        FROM iris.album a 
        LEFT JOIN iris.album_track a_t ON a.id = a_t.album_id
        LEFT JOIN iris.track t ON a_t.track_id = t.id
        WHERE a.is_main AND a.game_id = $1;
END;
$$ LANGUAGE plpgsql;

/*
    Create a function to get all the basic information of a game
    --> SELECT * FROM iris.get_game_info(%s);
*/

CREATE OR REPLACE FUNCTION iris.get_game_info(integer)
RETURNS TABLE (
    name text,
    slug text,
    complete boolean,
    parent_game int,
    category int,
    collection_id int,
    first_release_date date,
    rating double precision,
    popularity int,
    summary text
) AS $$
BEGIN
    RETURN QUERY SELECT g.name, g.slug, g.complete, g.parent_game, g.category, g.collection_id, g.first_release_date, g.rating, g.popularity, g.summary
        FROM iris.game g
        WHERE g.id = $1;
END;
$$ LANGUAGE plpgsql;