-- Adds German labels for scene_type and keeps them in sync for new/updated rows.
do $$
begin
  if not exists (
    select 1
    from information_schema.columns
    where table_schema = 'referee_ratings'
      and table_name = 'scenes'
      and column_name = 'scene_type_label_de'
  ) then
    alter table referee_ratings.scenes
      add column scene_type_label_de text;
  end if;
end $$;

update referee_ratings.scenes
set scene_type_label_de = case scene_type
  when 'PENALTY' then 'Elfmeter'
  when 'PENALTY_REVIEW' then 'Elfmeter-Check'
  when 'PENALTY_OVERTURNED' then 'Elfmeter zurueckgenommen'
  when 'FREE_KICK' then 'Freistoss'
  when 'INDIRECT_FREE_KICK' then 'Indirekter Freistoss'
  when 'DROP_BALL' then 'Schiedsrichterball'
  when 'FOUL' then 'Foul'
  when 'YELLOW_CARD' then 'Gelbe Karte'
  when 'SECOND_YELLOW' then 'Zweite Gelbe'
  when 'RED_CARD' then 'Rote Karte'
  when 'OFFSIDE' then 'Abseits'
  when 'GOAL' then 'Tor'
  when 'OFFSIDE_GOAL' then 'Tor im Abseits'
  when 'GOAL_DISALLOWED' then 'Tor aberkannt'
  when 'VAR_REVIEW' then 'VAR-Check'
  when 'VAR_DECISION' then 'VAR-Entscheidung'
  when 'HANDBALL' then 'Handspiel'
  when 'DENIED_GOALSCORING_OPPORTUNITY' then 'Notbremse (DOGSO)'
  when 'SUBSTITUTION' then 'Wechsel'
  when 'INJURY_STOPPAGE' then 'Verletzungspause'
  when 'TIME_WASTING' then 'Zeitspiel'
  when 'DISSENT' then 'Unsportliches Verhalten'
  when 'CORNER' then 'Ecke'
  when 'GOAL_KICK' then 'Abstoss'
  when 'THROW_IN' then 'Einwurf'
  when 'OTHER' then 'Sonstiges'
  else scene_type::text
end
where scene_type_label_de is null;

create or replace function referee_ratings.set_scene_type_label_de()
returns trigger
language plpgsql
as $$
begin
  new.scene_type_label_de = case new.scene_type
    when 'PENALTY' then 'Elfmeter'
    when 'PENALTY_REVIEW' then 'Elfmeter-Check'
    when 'PENALTY_OVERTURNED' then 'Elfmeter zurueckgenommen'
    when 'FREE_KICK' then 'Freistoss'
    when 'INDIRECT_FREE_KICK' then 'Indirekter Freistoss'
    when 'DROP_BALL' then 'Schiedsrichterball'
    when 'FOUL' then 'Foul'
    when 'YELLOW_CARD' then 'Gelbe Karte'
    when 'SECOND_YELLOW' then 'Zweite Gelbe'
    when 'RED_CARD' then 'Rote Karte'
    when 'OFFSIDE' then 'Abseits'
    when 'GOAL' then 'Tor'
    when 'OFFSIDE_GOAL' then 'Tor im Abseits'
    when 'GOAL_DISALLOWED' then 'Tor aberkannt'
    when 'VAR_REVIEW' then 'VAR-Check'
    when 'VAR_DECISION' then 'VAR-Entscheidung'
    when 'HANDBALL' then 'Handspiel'
    when 'DENIED_GOALSCORING_OPPORTUNITY' then 'Notbremse (DOGSO)'
    when 'SUBSTITUTION' then 'Wechsel'
    when 'INJURY_STOPPAGE' then 'Verletzungspause'
    when 'TIME_WASTING' then 'Zeitspiel'
    when 'DISSENT' then 'Unsportliches Verhalten'
    when 'CORNER' then 'Ecke'
    when 'GOAL_KICK' then 'Abstoss'
    when 'THROW_IN' then 'Einwurf'
    when 'OTHER' then 'Sonstiges'
    else new.scene_type::text
  end;
  return new;
end;
$$;

drop trigger if exists trg_scene_type_label_de on referee_ratings.scenes;
create trigger trg_scene_type_label_de
before insert or update of scene_type
on referee_ratings.scenes
for each row execute function referee_ratings.set_scene_type_label_de();
