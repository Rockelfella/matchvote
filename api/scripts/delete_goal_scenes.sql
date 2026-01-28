-- Delete GOAL scenes and their ratings.
-- Run inside a transaction if your environment does not auto-wrap scripts.

delete from referee_ratings.ratings
where scene_id in (
  select scene_id
  from referee_ratings.scenes
  where scene_type = 'GOAL'
);

delete from referee_ratings.scenes
where scene_type = 'GOAL';
