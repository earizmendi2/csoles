def migrate(cr, version):
    # Existing 18.0 profiles used computed user counts and had no model
    # configuration records. Backfill both additions after the new schema loads.
    cr.execute(
        """
        UPDATE res_profile AS profile
           SET count_users = (
               SELECT COUNT(*)
                 FROM res_profile_res_users_rel AS relation
                WHERE relation.res_profile_id = profile.id
           )
        """
    )
    cr.execute("UPDATE res_profile_model_access SET apply_form = TRUE")
    cr.execute(
        """
        INSERT INTO res_profile_model_access (
            profile_id, model_id, apply_form, apply_list, apply_kanban,
            disable_create, disable_edit, disable_delete
        )
        SELECT pairs.profile_id, pairs.model_id, TRUE, FALSE, FALSE,
               FALSE, FALSE, FALSE
          FROM (
                SELECT profile_id, model_id FROM res_profile_field
                UNION
                SELECT profile_id, model_id FROM res_profile_field_m2x
               ) AS pairs
         WHERE NOT EXISTS (
               SELECT 1
                 FROM res_profile_model_access AS config
                WHERE config.profile_id = pairs.profile_id
                  AND config.model_id = pairs.model_id
         )
        """
    )
    for table in ('res_profile_field', 'res_profile_field_m2x'):
        cr.execute(
            f"""
            UPDATE {table} AS rule
               SET profile_model_id = config.id
              FROM res_profile_model_access AS config
             WHERE config.profile_id = rule.profile_id
               AND config.model_id = rule.model_id
            """
        )
