def log_search_if_configured(*, player_id=None, server_id=None, nickname=None,
                             country_code=None, country_name=None,
                             parsed_obj=None, raw_response=None, request_meta=None):
    """Safe logger. In production this writes a row to MySQL; in dev it prints.

    To enable DB logging set the environment variables:
      LOG_DB_HOST, LOG_DB_USER, LOG_DB_PASS, LOG_DB_NAME

    The function must never raise.
    """
    try:
        summary = {
            'player_id': player_id,
            'server_id': server_id,
            'nickname': nickname,
            'country_code': country_code,
        }

        # If DB credentials provided, attempt to write to a simple `search_logs` table.
        import os
        import json
        db_host = 'webhosting3009.is.cc'
        db_user = 'frigussm_panel'
        db_pass = 'frigussm_panel'
        db_name = 'frigussm_nganba'

        if db_host and db_user and db_name:
            try:
                import pymysql
                conn = pymysql.connect(host=db_host, user=db_user, password=db_pass or '',
                                       database=db_name, charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
                with conn:
                    with conn.cursor() as cur:
                        # Ensure table exists (idempotent create)
                        cur.execute("""
                        CREATE TABLE IF NOT EXISTS search_logs (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            player_id VARCHAR(255),
                            server_id VARCHAR(255),
                            nickname VARCHAR(255),
                            country_code VARCHAR(64),
                            country_name VARCHAR(255),
                            parsed_obj JSON,
                            raw_response JSON,
                            request_meta JSON,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        ) CHARSET=utf8mb4;
                        """)

                        cur.execute(
                            "INSERT INTO search_logs (player_id, server_id, nickname, country_code, country_name, parsed_obj, raw_response, request_meta) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                            (str(player_id) if player_id is not None else None,
                             str(server_id) if server_id is not None else None,
                             nickname,
                             country_code,
                             country_name,
                             json.dumps(parsed_obj, default=str) if parsed_obj is not None else None,
                             json.dumps(raw_response, default=str) if raw_response is not None else None,
                             json.dumps(request_meta, default=str) if request_meta is not None else None)
                        )
                    conn.commit()
                return
            except Exception:
                # If DB write fails, fall through to printing summary
                pass

        # Fallback: print minimal info so local dev can see what's happening.
        print('[log_search_if_configured]', summary)
    except Exception:
        # swallow all errors
        pass
