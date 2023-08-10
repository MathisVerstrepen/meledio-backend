CREATE SCHEMA IF NOT EXISTS iris AUTHORIZATION supabase_admin;
GRANT USAGE ON SCHEMA iris TO postgres;
CREATE EXTENSION pg_trgm;

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
    "width" int,
    "blur_hash" text
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
    category text,
    collection_id int,
    first_release_date date,
    rating double precision,
    popularity int,
    summary text,
    n_tracks bigint
) AS $$
BEGIN
    RETURN QUERY SELECT g.name, g.slug, g.complete, g.parent_game, c.name, g.collection_id, g.first_release_date, g.rating, g.popularity, g.summary, 
        (SELECT COUNT(t.id) FROM iris.track t LEFT JOIN iris.album_track a_t ON t.id = a_t.track_id LEFT JOIN iris.album a ON a_t.album_id = a.id WHERE a.game_id = g.id AND a.is_main)
        FROM iris.game g
        LEFT JOIN iris.category c ON c.id = g.category
        WHERE g.id = $1;
END;
$$ LANGUAGE plpgsql;


/*
    Create a function to get all information about a company of a game ID
    --> SELECT * FROM iris.get_game_company(%s);
*/

CREATE OR REPLACE FUNCTION iris.get_game_company(integer)
RETURNS TABLE (
    company_id int,
    developer boolean,
    porting boolean,
    publisher boolean,
    supporting boolean,
    name text,
    slug text,
    description text,
    logo_id text
) AS $$
BEGIN
    RETURN QUERY SELECT i_c.company_id, i_c.developer, i_c.porting, i_c.publisher, i_c.supporting, c.name, c.slug, c.description, c.logo_id
        FROM iris.involved_companies i_c
        LEFT JOIN iris.company c ON c.id = i_c.company_id
        WHERE i_c.game_id = $1;
END;
$$ LANGUAGE plpgsql;

/*
    Create a function to get information about a collection
    --> SELECT * FROM iris.get_collection_info(%s);
*/

CREATE OR REPLACE FUNCTION iris.get_collection_info(integer)
RETURNS TABLE (
    game_id int,
    collection_name text,
    collection_slug text
) AS $$
BEGIN
    RETURN QUERY SELECT g.id, c.name, c.slug
        FROM iris.game g
        LEFT JOIN iris.collection c ON g.collection_id = c.id
        WHERE g.collection_id = $1;
END;
$$ LANGUAGE plpgsql;

/*
    Create a function to get a number of top rated collection and basic information about them
    --> SELECT * FROM iris.get_top_collections(%s);
*/

CREATE OR REPLACE FUNCTION iris.get_top_collections(integer, integer)
RETURNS TABLE (
    collection_id int,
    collection_name text,
    collection_slug text,
    game_id int,
    game_name text,
    image_id text,
    blur_hash text
) AS $$
BEGIN
    RETURN QUERY SELECT g.collection_id, c.name, c.slug, g.id, g.name, m.image_id, m.blur_hash
        FROM iris.game g
        JOIN (SELECT c.id, c.name, c.slug
                FROM iris.collection c
                JOIN iris.game g ON c.id = g.collection_id
                WHERE complete
                GROUP BY c.id
                HAVING AVG(rating) IS NOT null AND COUNT(*) > 2
                ORDER BY AVG(rating) DESC
                LIMIT $1 OFFSET $2) c ON c.id = g.collection_id
        JOIN iris.media m on g.id = m.game_id
        WHERE m."type" = 'cover';
END;
$$ LANGUAGE plpgsql;

/*
    Create a function to search for a game by name
    --> SELECT * FROM iris.search_game_by_name(%s, %s);
*/

CREATE index if not exists game_name_trgm_idx ON iris.game USING gin (name gin_trgm_ops);
-- DROP FUNCTION iris.search_game_by_name(text,integer) ;

CREATE OR REPLACE FUNCTION iris.search_game_by_name(text, int)
RETURNS TABLE (
    similarity real,
    game_id int,
    game_name text,
    game_slug text,
    game_complete boolean,
    cover_id text
) AS $$
BEGIN
    RETURN QUERY SELECT similarity(g.name, concat('%', $1, '%')), g.id, g.name, g.slug, g.complete, m.image_id
        FROM iris.game g
        left JOIN (select m.game_id, m.image_id from iris.media m where m."type" = 'cover') m ON g.id = m.game_id
        WHERE g.name ILIKE concat('%', $1, '%')
        ORDER BY similarity DESC
        LIMIT $2;
END;
$$ LANGUAGE plpgsql;


/*
    Create a function to get most popular tracks from a collection
    --> SELECT * FROM iris.get_collection_popular_tracks(%s, %s);
*/

CREATE OR REPLACE FUNCTION iris.get_collection_popular_tracks(integer, integer)
RETURNS TABLE (
    game_id int,
    game_title text,
    game_slug text,
    cover text,
    title text,
    slug text,
    file uuid,
    view_count int,
    like_count int,
    length int
) AS $$
BEGIN
    RETURN QUERY SELECT t.game_id, g.name , g.slug, m.image_id, t.title, t.slug, t.file, t.view_count, t.like_count, t.length FROM iris.track t
    	left JOIN (select m.game_id, m.image_id from iris.media m where m."type" = 'cover') m ON t.game_id = m.game_id
    	left join iris.game g on g.id = t.game_id
        WHERE t.game_id IN 
	        (SELECT id FROM iris.game WHERE iris.game.collection_id = $1)
        ORDER BY t.view_count DESC, t.id 
        LIMIT $2
        OFFSET 0;
END;
$$ LANGUAGE plpgsql;


/*
    Create a function to get most popular tracks from a game
    --> SELECT * FROM iris.get_game_popular_tracks(%s, %s);
*/

CREATE OR REPLACE FUNCTION iris.get_game_popular_tracks(integer, integer)
RETURNS TABLE (
    title text,
    slug text,
    file uuid,
    view_count int,
    like_count int,
    length int
) AS $$
BEGIN
    RETURN QUERY SELECT t.title, t.slug, t.file, t.view_count, t.like_count, t.length FROM iris.track t
        WHERE t.game_id = $1
        ORDER BY view_count DESC, id 
        LIMIT $2
        OFFSET 0;
END;
$$ LANGUAGE plpgsql;


/*
    Create a function to get all albums related to a game
    --> SELECT * FROM iris.get_game_albums(%s);
*/

CREATE OR REPLACE FUNCTION iris.get_game_albums(integer)
RETURNS TABLE (
    game_id int,
    game_name text,
    game_slug text,
    game_cover text,
    game_blurhash text,
    album_id int,
    album_name text,
    album_slug text,
    album_n_tracks bigint
) AS $$
BEGIN
    RETURN QUERY with gid as (select * from iris.game g where g.id = $1 or g.parent_game = $1)
    	SELECT a.game_id, gid.name, gid.slug, m.image_id, m.blur_hash, a.id, a.name, a.slug,
    	(SELECT COUNT(t.id) FROM iris.track t LEFT JOIN iris.album_track a_t ON t.id = a_t.track_id WHERE a.id = a_t.album_id)
    	FROM iris.album a
        join gid on gid.id = a.game_id 
        left JOIN (select m.game_id, m.image_id, m.blur_hash from iris.media m where m."type" = 'cover') m ON a.game_id = m.game_id
        WHERE gid.complete;
END;
$$ LANGUAGE plpgsql;


/*
    Create a function to get all similar games to a game
    --> SELECT * FROM iris.get_similar_games(%s);
*/

CREATE OR REPLACE FUNCTION iris.get_similar_games(integer)
RETURNS TABLE (
    game_id int,
    name text,
    slug text,
    cover_id text,
    cover_blurhash text
) AS $$
BEGIN
    RETURN QUERY with similar_games as (select ec.extra_id as id  from iris.extra_content ec 
		where ec.game_id = $1
			and ec."type" = 'similar_games')
		select sg.id, g."name", g.slug, m.image_id, m.blur_hash from iris.game g 
			right join similar_games sg on sg.id = g.id
			left JOIN (select m.game_id, m.image_id, m.blur_hash from iris.media m where m."type" = 'cover') m ON sg.id = m.game_id
			where g.complete;
END;
$$ LANGUAGE plpgsql;


/*
    Create a function to get all developers in the database
    --> SELECT * FROM iris.get_all_devs();
*/

CREATE OR REPLACE FUNCTION iris.get_all_devs()
RETURNS TABLE (
    id int,
    name text
) AS $$
BEGIN
    RETURN QUERY select distinct c.id, c.name
    	from iris.company c 
    	left join iris.involved_companies ic on c.id = ic.company_id 
    	where ic.developer 
    	order by c.name;
END;
$$ LANGUAGE plpgsql;


/*
    Create a function to get all genres and the number of games in each genre
    --> SELECT * FROM iris.get_genres();
*/

CREATE OR REPLACE FUNCTION iris.get_genres()
RETURNS TABLE (
    name text,
    count bigint
) AS $$
BEGIN
    RETURN QUERY select g.name, count(g.game_id) from iris.genre g 
		group by g.name 
		order by count desc, g.name;
END;
$$ LANGUAGE plpgsql;


/*
    Create a function to get all categories and the number of games in each genre
    --> SELECT * FROM iris.get_categories();
*/

CREATE OR REPLACE FUNCTION iris.get_categories()
RETURNS TABLE (
	id int,
    name text,
    count bigint
) AS $$
BEGIN
    RETURN QUERY select c.id, c.name, count(c.id) from iris.category c 
		left join iris.game g on g.category = c.id 
		group by c.id
		order by count desc, c.name;
END;
$$ LANGUAGE plpgsql;


/*
    Create a function to get search results
    --> SELECT * FROM iris.search_games();
*/


CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE OR REPLACE FUNCTION iris.search_games(
    _game_name TEXT,
    _category INT[], _company_id INT[], _genre_name TEXT[], 
    _rating_lower_bound REAL, _rating_upper_bound REAL, 
    _release_date_lower_bound DATE, _release_date_upper_bound DATE,
    _limit INT, _offset INT, _order INT
)
RETURNS TABLE(
    id INT,
    name TEXT,
    slug text,
    complete boolean,
    rating DOUBLE precision,
    release_date date,
    cover text,
    blurhash text
)
AS $$
BEGIN
    RETURN QUERY
    SELECT sub.id, sub.name, sub.slug, sub.complete, sub.rating, sub.first_release_date, sub.image_id, sub.blur_hash
    FROM (
        SELECT distinct g.id as id, g.name as name, g.slug as slug, g.complete as complete, g.rating as rating, g.first_release_date as first_release_date, m.image_id as image_id, m.blur_hash as blur_hash,
            CASE WHEN _order = 1 THEN g.name END AS sort_name_asc,
            CASE WHEN _order = 2 THEN g.name END AS sort_name_desc,
            CASE WHEN _order = 3 THEN g.rating END AS sort_rating_asc,
            CASE WHEN _order = 4 THEN g.rating END AS sort_rating_desc,
            CASE WHEN _order = 5 THEN g.first_release_date END AS sort_date_asc,
            CASE WHEN _order = 6 THEN g.first_release_date END AS sort_date_desc
        FROM iris.game AS g
        LEFT JOIN iris.involved_companies AS ic ON ic.game_id = g.id
        LEFT JOIN iris.genre AS g2 ON g.id = g2.game_id
        LEFT JOIN (select m.game_id, m.image_id, m.blur_hash from iris.media m where m."type" = 'cover') m ON g.id = m.game_id
        WHERE 
            (unaccent(lower(g.name)) ILIKE unaccent(lower('%' || _game_name || '%')))
            AND (array_length(_category, 1) IS NULL OR g.category = ANY(_category))
            AND ic.developer
            AND (array_length(_company_id, 1) IS NULL OR ic.company_id = ANY(_company_id))
            AND (array_length(_genre_name, 1) IS NULL OR g2."name" = ANY(_genre_name))
            AND g.rating >= _rating_lower_bound AND g.rating <= _rating_upper_bound
            AND g.first_release_date >= _release_date_lower_bound AND g.first_release_date <= _release_date_upper_bound
    ) sub
    ORDER BY 
        sort_name_asc ASC NULLS LAST,
        sort_name_desc DESC NULLS LAST,
        sort_rating_asc ASC NULLS LAST,
        sort_rating_desc DESC NULLS LAST,
        sort_date_asc ASC NULLS LAST,
        sort_date_desc DESC NULLS LAST
    limit _limit offset _offset;
END; $$ 
LANGUAGE plpgsql;

