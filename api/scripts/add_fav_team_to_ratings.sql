-- Optional field for user team sympathy on ratings.
ALTER TABLE referee_ratings.ratings
  ADD COLUMN IF NOT EXISTS fav_team TEXT NULL;
