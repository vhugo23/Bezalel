export interface paths {
    "/api/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_api_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/plans": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Plan */
        post: operations["create_plan_api_plans_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Start Session */
        post: operations["start_session_api_sessions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sessions/{session_id}/turns": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Take Turn
         * @description Typed fallback. The voice path uses WS /ws/voice/{session_id}.
         */
        post: operations["take_turn_api_sessions__session_id__turns_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sessions/{session_id}/probe": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Probe
         * @description Fallback and tests. The live path is WS /ws/board/{session_id}.
         */
        post: operations["probe_api_sessions__session_id__probe_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sessions/{session_id}/end": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * End Session
         * @description Returns immediately. Progress and results arrive on GET /api/sessions/{id}/events (SSE).
         */
        post: operations["end_session_api_sessions__session_id__end_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sessions/{session_id}/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Session Events
         * @description Server-Sent Events: evaluator_started, evaluator_done, evaluator_failed, grading_complete.
         *     Replays events that already happened, and closes after grading_complete.
         */
        get: operations["session_events_api_sessions__session_id__events_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sessions/{session_id}/report": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Report */
        get: operations["report_api_sessions__session_id__report_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sessions/{session_id}/debrief": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Debrief
         * @description What stood out, what went fine, and where to learn each gap. Shown when the interview ends.
         */
        get: operations["debrief_api_sessions__session_id__debrief_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sessions/{session_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Delete Session
         * @description Consent: removes every stored row for this session.
         */
        delete: operations["delete_session_api_sessions__session_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/skills": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Skills */
        get: operations["skills_api_skills_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/lessons/{skill_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Lesson */
        get: operations["get_lesson_api_lessons__skill_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/retests": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Retest */
        post: operations["create_retest_api_retests_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/mastery": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Mastery */
        get: operations["mastery_api_mastery_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/metrics/{session_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Metrics
         * @description Measured values only. Fields stay null until something was measured.
         */
        get: operations["metrics_api_metrics__session_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sessions/{sid}/socket-ticket": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Socket Ticket */
        post: operations["socket_ticket_api_v2_sessions__sid__socket_ticket_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/account/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Account Export */
        get: operations["account_export_api_v2_account_export_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sessions/{sid}/local-speech/jobs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Local Speech Start */
        post: operations["local_speech_start_api_v2_sessions__sid__local_speech_jobs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sessions/{sid}/local-speech/jobs/{jid}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Local Speech Finish */
        post: operations["local_speech_finish_api_v2_sessions__sid__local_speech_jobs__jid__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/history": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** History */
        get: operations["history_api_v2_history_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_api_v2_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/plans": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Plan */
        post: operations["plan_api_v2_plans_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/plans/jobs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Plan Job */
        post: operations["plan_job_api_v2_plans_jobs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/plans/{pid}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Plan */
        get: operations["get_plan_api_v2_plans__pid__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/users/{user_id}/sources": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Source List */
        get: operations["source_list_api_v2_users__user_id__sources_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sources": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Source Create */
        post: operations["source_create_api_v2_sources_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sources/upload": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Source Upload */
        post: operations["source_upload_api_v2_sources_upload_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sources/github": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Source Github */
        post: operations["source_github_api_v2_sources_github_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sources/{source_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Source Read */
        get: operations["source_read_api_v2_sources__source_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sources/{source_id}/extract": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Source Extract */
        post: operations["source_extract_api_v2_sources__source_id__extract_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sources/{source_id}/scan": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Source Scan */
        post: operations["source_scan_api_v2_sources__source_id__scan_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sources/{source_id}/ats": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Ats Read */
        get: operations["ats_read_api_v2_sources__source_id__ats_get"];
        put?: never;
        /** Ats Start */
        post: operations["ats_start_api_v2_sources__source_id__ats_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sources/{source_id}/ats/apply": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Ats Apply */
        post: operations["ats_apply_api_v2_sources__source_id__ats_apply_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sources/{source_id}/pdf": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Source Pdf */
        get: operations["source_pdf_api_v2_sources__source_id__pdf_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sources/{source_id}/confirm": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Source Confirm */
        post: operations["source_confirm_api_v2_sources__source_id__confirm_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Start */
        post: operations["start_api_v2_sessions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sessions/{sid}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Session */
        get: operations["session_api_v2_sessions__sid__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sessions/{sid}/lab": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Lab Action */
        post: operations["lab_action_api_v2_sessions__sid__lab_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sessions/{sid}/pause": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Pause */
        post: operations["pause_api_v2_sessions__sid__pause_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sessions/{sid}/hint": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Hint */
        post: operations["hint_api_v2_sessions__sid__hint_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sessions/{sid}/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Events */
        get: operations["events_api_v2_sessions__sid__events_get"];
        put?: never;
        /** Append */
        post: operations["append_api_v2_sessions__sid__events_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sessions/{sid}/turns": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Turn */
        post: operations["turn_api_v2_sessions__sid__turns_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sessions/{sid}/reply-complete": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reply Complete */
        post: operations["reply_complete_api_v2_sessions__sid__reply_complete_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sessions/{sid}/board/elements": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Board Elements */
        post: operations["board_elements_api_v2_sessions__sid__board_elements_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sessions/{sid}/board": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Board */
        post: operations["board_api_v2_sessions__sid__board_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sessions/{sid}/end": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** End */
        post: operations["end_api_v2_sessions__sid__end_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sessions/{sid}/report": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Report */
        get: operations["report_api_v2_sessions__sid__report_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sessions/{sid}/metrics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Metrics */
        get: operations["metrics_api_v2_sessions__sid__metrics_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sessions/{sid}/lesson": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Lesson */
        get: operations["lesson_api_v2_sessions__sid__lesson_get"];
        put?: never;
        /**
         * Generate Lesson
         * @deprecated
         */
        post: operations["generate_lesson_api_v2_sessions__sid__lesson_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sessions/{sid}/lesson/jobs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Lesson Job */
        get: operations["lesson_job_api_v2_sessions__sid__lesson_jobs_get"];
        put?: never;
        /** Enqueue Lesson */
        post: operations["enqueue_lesson_api_v2_sessions__sid__lesson_jobs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/jobs/{jid}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Job */
        get: operations["get_job_api_v2_jobs__jid__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/jobs/{jid}/retry": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Retry Job */
        post: operations["retry_job_api_v2_jobs__jid__retry_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/jobs/{jid}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Cancel Job */
        post: operations["cancel_job_api_v2_jobs__jid__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/retests": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Retest */
        post: operations["retest_api_v2_retests_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sessions/{sid}/pair": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Pair */
        post: operations["pair_api_v2_sessions__sid__pair_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/artifacts/{aid}/png": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Artifact */
        get: operations["artifact_api_v2_artifacts__aid__png_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sessions/{sid}/audio": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Audio */
        post: operations["audio_api_v2_sessions__sid__audio_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sessions/{sid}/speech/{seq}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Speech */
        get: operations["speech_api_v2_sessions__sid__speech__seq__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Me */
        get: operations["me_api_v2_auth_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/auth/register": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Register */
        post: operations["register_api_v2_auth_register_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Login */
        post: operations["login_api_v2_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Logout */
        post: operations["logout_api_v2_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** Account */
        Account: {
            /** Id */
            id: string;
            /** Name */
            name: string;
            /** Email */
            email: string;
        };
        /** Annotation */
        Annotation: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "circle" | "arrow" | "underline" | "highlight" | "sticky" | "cross" | "check";
            /**
             * Severity
             * @enum {string}
             */
            severity: "good" | "info" | "probe" | "problem";
            /** Speech */
            speech: string;
            /** Target */
            target: string;
            /** Id */
            id: string;
            /** Geometry */
            geometry: {
                [key: string]: number;
            };
            /** Target Seq */
            target_seq: number;
            /** Event Seq */
            event_seq: number;
        };
        /** AtsApply */
        AtsApply: {
            /** Job Id */
            job_id?: string | null;
            /** Suggestion Ids */
            suggestion_ids: number[];
        };
        /** AtsCategoryResult */
        AtsCategoryResult: {
            /**
             * Id
             * @enum {string}
             */
            id: "format" | "sections" | "keywords" | "impact" | "clarity";
            /** Rating */
            rating: number;
            /** Weight */
            weight: number;
            /** Findings */
            findings: components["schemas"]["AtsFinding"][];
        };
        /** AtsCoverage */
        AtsCoverage: {
            /** Quote */
            quote: string;
            /** Term */
            term: string;
            /**
             * Level
             * @enum {string}
             */
            level: "required" | "preferred";
            /** Mentioned */
            mentioned: boolean;
            /** Resume Quote */
            resume_quote?: string | null;
            /**
             * Status
             * @enum {string}
             */
            status: "found" | "evidence" | "missing";
        };
        /** AtsFacts */
        AtsFacts: {
            /** Words */
            words: number;
            /** Email */
            email: boolean;
            /** Phone */
            phone: boolean;
            /** Sections */
            sections: string[];
        };
        /** AtsFinding */
        AtsFinding: {
            /** Issue */
            issue: string;
            /** Quote */
            quote?: string | null;
        };
        /** AtsRequest */
        AtsRequest: {
            /** Job Id */
            job_id?: string | null;
        };
        /** AtsReview */
        AtsReview: {
            /** Resume Id */
            resume_id: string;
            /** Job Id */
            job_id?: string | null;
            /** Job Title */
            job_title?: string | null;
            /** Score */
            score?: number | null;
            /** Categories */
            categories: components["schemas"]["AtsCategoryResult"][];
            facts: components["schemas"]["AtsFacts"];
            /** Suggestions */
            suggestions: components["schemas"]["AtsSuggestion"][];
            /** Rejected */
            rejected: number;
            /** Coverage */
            coverage?: components["schemas"]["AtsCoverage"][];
            /** Provider */
            provider: string;
            /** Rubric Version */
            rubric_version: string;
            /** Source Job Id */
            source_job_id: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /** AtsSuggestion */
        AtsSuggestion: {
            /** Id */
            id: number;
            /**
             * Category
             * @enum {string}
             */
            category: "format" | "sections" | "keywords" | "impact" | "clarity";
            /** Original */
            original: string;
            /** Replacement */
            replacement: string;
            /** Reason */
            reason: string;
            /** Start */
            start: number;
            /** End */
            end: number;
        };
        /** AuthState */
        AuthState: {
            /**
             * Enabled
             * @default true
             */
            enabled: boolean;
            user?: components["schemas"]["Account"] | null;
        };
        /**
         * BoardElement
         * @description One saved version of an Excalidraw element. A later version of the same id
         *     replaces it; `isDeleted` versions remove it from the board.
         */
        BoardElement: {
            /** Id */
            id: string;
            /** Version */
            version: number;
            /** Element */
            element: {
                [key: string]: unknown;
            };
        };
        /** BoardElementsInput */
        BoardElementsInput: {
            /** Step */
            step: number;
            /** Elements */
            elements: components["schemas"]["BoardElement"][];
        };
        /** BoardInput */
        BoardInput: {
            /** Elements */
            elements: components["schemas"]["BoardElement"][];
            /** Png */
            png: string;
        };
        /** BoardResult */
        BoardResult: {
            /** Annotations */
            annotations: components["schemas"]["Annotation"][];
            /** Source */
            source: string;
            /** Artifact Id */
            artifact_id: string;
            /** Stroke Ids */
            stroke_ids?: string[];
        };
        /** CheckedClaim */
        CheckedClaim: {
            /** Text */
            text: string;
            /**
             * Polarity
             * @enum {string}
             */
            polarity: "strength" | "gap" | "neutral";
            /** Evidence Seq */
            evidence_seq: number[];
            /** Quotes */
            quotes?: string[];
            /**
             * Skill Id
             * @default sw.system_design
             */
            skill_id: string;
            /**
             * Rule
             * @default quoted_turn
             * @enum {string}
             */
            rule: "quoted_turn" | "board_explanation" | "drawing" | "question" | "tool_action";
            /** Id */
            id: string;
            /** Evaluator */
            evaluator: string;
            /** Check Status */
            check_status: string;
            /** Check Reason */
            check_reason: string;
        };
        /** Credentials */
        Credentials: {
            /** Email */
            email: string;
            /** Password */
            password: string;
        };
        /** CriterionResult */
        CriterionResult: {
            /** Id */
            id: string;
            /** Score */
            score: number;
            /** Evidence Quote */
            evidence_quote: string;
            /** Evidence Span */
            evidence_span: number[];
            /**
             * Evidence Probe Seqs
             * @description Probe log steps (seq) that support the score, for process criteria. Show as 'you measured n1, then n2, then swapped D1'.
             */
            evidence_probe_seqs?: number[];
            /** Rationale */
            rationale: string;
        };
        /** DebriefGap */
        DebriefGap: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "skill" | "unanswered";
            /** Requirement Id */
            requirement_id?: string | null;
            /** Title */
            title: string;
            /** Level */
            level?: ("required" | "preferred") | null;
            /**
             * Result
             * @enum {string}
             */
            result: "unknown" | "partial" | "no_answer";
            /**
             * Evidence Quote
             * @description The candidate's own words, checked to appear in their answer.
             */
            evidence_quote: string;
            /** Turn */
            turn?: number | null;
            /**
             * Resources
             * @default []
             */
            resources: components["schemas"]["Resource"][];
            /**
             * Search Hint
             * @description Set when no resource matched. A search term, not a link.
             */
            search_hint?: string | null;
            /** Tip */
            tip?: string | null;
        };
        /** DebriefResponse */
        DebriefResponse: {
            /** Session Id */
            session_id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "in_progress" | "interview_finished" | "ended_early";
            /** Ended Early */
            ended_early: boolean;
            /** End Reason */
            end_reason?: string | null;
            /** Summary */
            summary: string;
            /** Gaps */
            gaps: components["schemas"]["DebriefGap"][];
            /** Strengths */
            strengths: components["schemas"]["DebriefStrength"][];
            meter?: components["schemas"]["MeterState"] | null;
            /** Resources Note */
            resources_note: string;
            /** Library Reviewed */
            library_reviewed: boolean;
        };
        /** DebriefStrength */
        DebriefStrength: {
            /** Requirement Id */
            requirement_id: string;
            /** Title */
            title: string;
            /** Evidence Quote */
            evidence_quote: string;
        };
        /** DeleteResponse */
        DeleteResponse: {
            /** Session Id */
            session_id: string;
            /** Deleted Rows */
            deleted_rows: number;
        };
        /** EndSessionResponse */
        EndSessionResponse: {
            /**
             * Status
             * @constant
             */
            status: "grading";
            /** Session Id */
            session_id: string;
            /** Events Url */
            events_url: string;
        };
        /** EvaluatorOutput */
        EvaluatorOutput: {
            /** Answer Id */
            answer_id: string;
            /** Rubric Id */
            rubric_id: string;
            /** Criteria */
            criteria: components["schemas"]["CriterionResult"][];
            /** Skill Flags */
            skill_flags: string[];
            /** Confidence */
            confidence: number;
            /**
             * Needs Review
             * @default false
             */
            needs_review: boolean;
        };
        /** Event */
        Event: {
            /** Session Id */
            session_id: string;
            /** Seq */
            seq: number;
            /** Kind */
            kind: string;
            /** Actor */
            actor: string;
            /** Step */
            step: number | null;
            /** Payload */
            payload: {
                [key: string]: unknown;
            };
            /**
             * Ts
             * Format: date-time
             */
            ts: string;
        };
        /** EventInput */
        EventInput: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "turn" | "stroke" | "step" | "note" | "interrupted";
            /**
             * Step
             * @default 0
             */
            step: number;
            /** Payload */
            payload?: {
                [key: string]: unknown;
            };
        };
        /** GapSummary */
        GapSummary: {
            /** Id */
            id: string;
            /** Skill Id */
            skill_id: string;
            /** Text */
            text: string;
            /** Evidence Seq */
            evidence_seq: number[];
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** Health */
        Health: {
            /** Status */
            status: string;
            /** Schema Version */
            schema_version: string;
            /** Demo */
            demo: boolean;
            /** Voice Ready */
            voice_ready: boolean;
            /**
             * Test Environment
             * @default false
             */
            test_environment: boolean;
        };
        /** History */
        History: {
            /** Latest Plan Id */
            latest_plan_id?: string | null;
            /** Sessions */
            sessions?: components["schemas"]["HistoryEntry"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** HistoryEntry */
        HistoryEntry: {
            /** Id */
            id: string;
            /** Title */
            title: string;
            /** Status */
            status: string;
            /** Step */
            step: number;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Ended At */
            ended_at?: string | null;
        };
        /** Intake */
        Intake: {
            /** User Id */
            user_id: string;
            /**
             * Name
             * @default Joshua
             */
            name: string;
            /** Role */
            role: string;
            /** Companies */
            companies: string[];
            /** Struggles */
            struggles: string[];
            /** Question */
            question: string;
            /**
             * Link
             * @default
             */
            link: string;
            /** Source Ids */
            source_ids?: string[];
        };
        /** LabAction */
        LabAction: {
            /** Request Id */
            request_id: string;
            /** Revision */
            revision: number;
            /** Step */
            step: number;
            /**
             * Kind
             * @enum {string}
             */
            kind: "command" | "edit" | "part" | "browser";
            /** Text */
            text: string;
        };
        /** Lesson */
        Lesson: {
            /** Id */
            id?: string | null;
            /**
             * Title
             * @default Your next practice
             */
            title: string;
            /** Body */
            body: string;
            /** Reason */
            reason: string;
            /** Evidence Seq */
            evidence_seq: number[];
            /** Skill Id */
            skill_id?: string | null;
            /** Claim Id */
            claim_id?: string | null;
            /**
             * Ai Generated
             * @default false
             */
            ai_generated: boolean;
            /**
             * Practice
             * @default
             */
            practice: string;
            /**
             * Retest Ready
             * @default false
             */
            retest_ready: boolean;
            /**
             * Validation Label
             * @default Model-reviewed conceptual exercise; no deterministic correctness guarantee
             */
            validation_label: string;
        };
        /** LessonResponse */
        LessonResponse: {
            /** Skill Id */
            skill_id: string;
            /** Body */
            body: string;
            /**
             * Ai Generated
             * @default true
             */
            ai_generated: boolean;
        };
        /** LocalSpeechFinish */
        LocalSpeechFinish: {
            /**
             * Status
             * @enum {string}
             */
            status: "succeeded" | "failed";
            /**
             * Text
             * @default
             */
            text: string;
            /**
             * Latency Ms
             * @default 0
             */
            latency_ms: number;
        };
        /** LocalSpeechJob */
        LocalSpeechJob: {
            /** Id */
            id: string;
            /**
             * Text
             * @default
             */
            text: string;
        };
        /** LocalSpeechStart */
        LocalSpeechStart: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "stt" | "tts";
            /** Seq */
            seq?: number | null;
        };
        /** MasteryPoint */
        MasteryPoint: {
            /** Day */
            day: string;
            /** Mastery */
            mastery: number;
            /** N */
            n: number;
        };
        /** MasteryResponse */
        MasteryResponse: {
            /** User Id */
            user_id: string;
            /** Series */
            series: components["schemas"]["MasterySeries"][];
        };
        /** MasterySeries */
        MasterySeries: {
            /** Skill Id */
            skill_id: string;
            /** Points */
            points: components["schemas"]["MasteryPoint"][];
        };
        /** MeterState */
        MeterState: {
            /** Score */
            score: number;
            /** Threshold */
            threshold: number;
            /**
             * Level
             * @enum {string}
             */
            level: "ok" | "wrapping_up" | "ended";
            /**
             * Unanswered
             * @description Questions the candidate ignored so far.
             * @default 0
             */
            unanswered: number;
            /**
             * Checked
             * @description False when the check could not run for the latest answer (model error or timeout), so nothing was judged.
             * @default true
             */
            checked: boolean;
        };
        /** Metrics */
        Metrics: {
            /** Rows */
            rows: {
                [key: string]: unknown;
            }[];
            /** Hypertables */
            hypertables: string[];
            /** Aggregates */
            aggregates: string[];
            /** Mastery */
            mastery?: {
                [key: string]: unknown;
            }[];
        };
        /** MetricsResponse */
        MetricsResponse: {
            /** Session Id */
            session_id: string;
            /** Stt Ms */
            stt_ms?: number | null;
            /** Llm First Token Ms */
            llm_first_token_ms?: number | null;
            /** Tts First Audio Ms */
            tts_first_audio_ms?: number | null;
            /** Turn Total Ms */
            turn_total_ms?: number | null;
            /** Evaluator Fleet Ms */
            evaluator_fleet_ms?: number | null;
            /**
             * Samples
             * @default 0
             */
            samples: number;
        };
        /** PairResult */
        PairResult: {
            /** Code */
            code: string;
            /** Session Id */
            session_id: string;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
        };
        /** PauseInput */
        PauseInput: {
            /** Paused */
            paused: boolean;
        };
        /** Plan */
        Plan: {
            /** Id */
            id: string;
            intake: components["schemas"]["Intake"];
            /** Primary Domain */
            primary_domain: string;
            /** Skills */
            skills: components["schemas"]["Skill"][];
            /** Tracks */
            tracks: components["schemas"]["Track"][];
            /** Source */
            source: string;
            /** Foundations */
            foundations?: {
                [key: string]: string;
            }[];
        };
        /** PlanRequest */
        PlanRequest: {
            /** Job Posting */
            job_posting: string;
            /** Resume */
            resume: string;
            /** User Id */
            user_id?: string | null;
        };
        /** PlanResponse */
        PlanResponse: {
            /** Plan Id */
            plan_id: string;
            /** Topics */
            topics: string[];
            /** Questions */
            questions: string[];
            /** Scenario Ids */
            scenario_ids: string[];
            /**
             * Project
             * @default
             */
            project: string;
            /**
             * Requirements
             * @description Skills from the posting. Empty means the patience meter is off.
             */
            requirements?: components["schemas"]["Requirement"][];
            /**
             * Degraded
             * @description True when the model plan failed and generic questions were used.
             * @default false
             */
            degraded: boolean;
            /**
             * Memories
             * @description What PrepCrew remembers about this user from earlier sessions (Backboard). Empty for a first session.
             */
            memories?: string[];
        };
        /** ProbeEvent */
        ProbeEvent: {
            /** Event Id */
            event_id: string;
            /** Seq */
            seq: number;
            /** T */
            t: string;
            /** Session Id */
            session_id: string;
            /** Scenario Id */
            scenario_id: string;
            /**
             * Action
             * @enum {string}
             */
            action: "probe_voltage" | "probe_continuity" | "swap_part" | "isolate_section" | "power_cycle";
            /** Node */
            node?: string | null;
            /** Value */
            value?: number | null;
            /**
             * Unit
             * @default none
             * @enum {string}
             */
            unit: "V" | "ohm" | "none";
        };
        /**
         * ProbeRequest
         * @description Client sends the action only. seq, value and t are always set by the server.
         */
        ProbeRequest: {
            /**
             * Action
             * @default probe_voltage
             * @enum {string}
             */
            action: "probe_voltage" | "probe_continuity" | "swap_part" | "isolate_section" | "power_cycle";
            /** Node */
            node?: string | null;
            /**
             * Scenario Id
             * @description Defaults to the session's current scenario.
             */
            scenario_id?: string | null;
        };
        /** Registration */
        Registration: {
            /** Email */
            email: string;
            /** Password */
            password: string;
            /** Name */
            name: string;
        };
        /** ReplyAck */
        ReplyAck: {
            /** Seq */
            seq: number;
        };
        /** Report */
        Report: {
            /** Session Id */
            session_id: string;
            /** Status */
            status: string;
            /** Claims */
            claims: components["schemas"]["CheckedClaim"][];
            /** Evaluators */
            evaluators: {
                [key: string]: unknown;
            }[];
            /** Demo */
            demo: boolean;
            /** Overall */
            overall?: number | null;
            /** Scores */
            scores?: components["schemas"]["SkillScore"][];
            next_gap?: components["schemas"]["GapSummary"] | null;
            /**
             * Partial
             * @default false
             */
            partial: boolean;
            /** Rubric Version */
            rubric_version?: string | null;
        };
        /** ReportResponse */
        ReportResponse: {
            /** Session Id */
            session_id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "not_ended" | "grading" | "graded";
            /** Results */
            results: components["schemas"]["EvaluatorOutput"][];
            /** Skill Flags */
            skill_flags: string[];
        };
        /** Requirement */
        Requirement: {
            /** Id */
            id: string;
            /** Text */
            text: string;
            /**
             * Level
             * @enum {string}
             */
            level: "required" | "preferred";
        };
        /** Resource */
        Resource: {
            /** Id */
            id: string;
            /** Title */
            title: string;
            /** Url */
            url: string;
            /** Source */
            source: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "tutorial" | "video" | "docs" | "reference";
            /**
             * Level
             * @enum {string}
             */
            level: "beginner" | "intermediate";
            /**
             * Why
             * @description What the page covers, from reading it. Not a promise it fixes the gap.
             */
            why: string;
            /** Caveat */
            caveat?: string | null;
            /**
             * Reviewed
             * @description True only after a person has reviewed the link and its fit.
             * @default false
             */
            reviewed: boolean;
            /**
             * Verified On
             * @description The day the link was opened and its content read.
             */
            verified_on: string;
        };
        /** RetestInput */
        RetestInput: {
            /** Session Id */
            session_id: string;
        };
        /** RetestRequest */
        RetestRequest: {
            /** Session Id */
            session_id: string;
            /** Skill Ids */
            skill_ids: string[];
        };
        /** Session */
        Session: {
            /** Id */
            id: string;
            /** Track Id */
            track_id: string;
            /** Title */
            title: string;
            /** Status */
            status: string;
            /** Step */
            step: number;
            /** Opening */
            opening: string;
            /** Demo */
            demo: boolean;
            /** Events */
            events: components["schemas"]["Event"][];
            board_review?: components["schemas"]["BoardResult"] | null;
            /**
             * Domain
             * @default sw
             */
            domain: string;
            /**
             * Engine Id
             * @default conceptual
             */
            engine_id: string;
            /** Steps */
            steps?: components["schemas"]["SessionStep"][];
            /**
             * Paused
             * @default false
             */
            paused: boolean;
            /** Engine State */
            engine_state?: {
                [key: string]: unknown;
            };
        };
        /** SessionStartRequest */
        SessionStartRequest: {
            /** Plan Id */
            plan_id: string;
            /** User Id */
            user_id: string;
            /**
             * Consent
             * @description Must be true. Sessions without consent are rejected.
             */
            consent: boolean;
            /**
             * Strict
             * @description False: the patience meter wraps the interview up but never ends it. For demos and testers.
             * @default true
             */
            strict: boolean;
        };
        /** SessionStartResponse */
        SessionStartResponse: {
            /** Session Id */
            session_id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "interview" | "retest";
            /**
             * Pair Code
             * @description Short code the iPad enters to join /ws/board/{session_id}.
             */
            pair_code: string;
            /** Voice Token */
            voice_token?: string | null;
            /**
             * Strict
             * @default true
             */
            strict: boolean;
            /**
             * State
             * @default intake
             * @enum {string}
             */
            state: "intake" | "interview" | "walkthrough" | "drill" | "debrief" | "lesson" | "retest";
            /**
             * Opening
             * @description First interviewer question, interview sessions only.
             */
            opening?: string | null;
            /**
             * Recalled
             * @description Memories from earlier sessions used for this one. Show as 'Picking up from last time'.
             */
            recalled?: string[];
        };
        /** SessionStep */
        SessionStep: {
            /** Idx */
            idx: number;
            /** Title */
            title: string;
            /**
             * Surface
             * @default voice
             * @enum {string}
             */
            surface: "voice" | "whiteboard" | "star" | "terminal" | "editor" | "schematic" | "browser" | "pi3d";
            /** Task */
            task: string;
            /** Config */
            config?: {
                [key: string]: unknown;
            };
            /** Hints */
            hints?: string[];
            /** Success */
            success?: {
                [key: string]: unknown;
            };
            /** Rubric Ids */
            rubric_ids?: string[];
        };
        /** Skill */
        Skill: {
            /** Id */
            id: string;
            /** Domain */
            domain: string;
            /** Name */
            name: string;
            /** Score */
            score: number | null;
            /** Target */
            target: number;
            /**
             * Estimate
             * @default false
             */
            estimate: boolean;
        };
        /** SkillNode */
        SkillNode: {
            /** Skill Id */
            skill_id: string;
            /** Title */
            title: string;
            /** Prerequisites */
            prerequisites: string[];
            /**
             * Mastery
             * @description 0..1, null when never graded
             */
            mastery?: number | null;
        };
        /** SkillScore */
        SkillScore: {
            /** Skill Id */
            skill_id: string;
            /** Name */
            name: string;
            /** Score */
            score: number;
            /** Previous */
            previous?: number | null;
            /** Delta */
            delta?: number | null;
            /** Previous Session Id */
            previous_session_id?: string | null;
            /** Previous Evidence Seq */
            previous_evidence_seq?: number[];
            /** Claim Ids */
            claim_ids: string[];
        };
        /** SkillsResponse */
        SkillsResponse: {
            /** User Id */
            user_id: string | null;
            /** Nodes */
            nodes: components["schemas"]["SkillNode"][];
        };
        /** SocketTicket */
        SocketTicket: {
            /** Token */
            token: string;
            /**
             * Expires In Seconds
             * @default 45
             */
            expires_in_seconds: number;
        };
        /** SocketTicketInput */
        SocketTicketInput: {
            /**
             * Channel
             * @enum {string}
             */
            channel: "events" | "voice";
        };
        /** SourceConfirmation */
        SourceConfirmation: {
            /** Fact Indices */
            fact_indices: number[];
        };
        /** SourceDocument */
        SourceDocument: {
            /** Id */
            id: string;
            /** User Id */
            user_id: string;
            /** Kind */
            kind: string;
            /** Title */
            title: string;
            /** Body */
            body: string;
            /** Extracted */
            extracted: {
                [key: string]: unknown;
            };
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /** SourceInput */
        SourceInput: {
            /** User Id */
            user_id: string;
            /**
             * Kind
             * @default notes
             * @enum {string}
             */
            kind: "resume" | "repo" | "job_posting" | "notes" | "other";
            /** Title */
            title: string;
            /** Body */
            body: string;
        };
        /** SourceLinkInput */
        SourceLinkInput: {
            /** User Id */
            user_id: string;
            /** Url */
            url: string;
        };
        /** SourceList */
        SourceList: {
            /** Sources */
            sources: components["schemas"]["SourceDocument"][];
        };
        /** Start */
        Start: {
            /** Track Id */
            track_id: string;
            /** Consent */
            consent: boolean;
        };
        /** Track */
        Track: {
            /** Id */
            id: string;
            /** Domain */
            domain: string;
            /** Title */
            title: string;
            /** Summary */
            summary: string;
            /** Layer */
            layer: number;
            /** Ready */
            ready: boolean;
            /** Reason */
            reason?: string | null;
            /**
             * Recommended
             * @default false
             */
            recommended: boolean;
            /** Priority Reason */
            priority_reason?: string | null;
            next_focus?: components["schemas"]["TrackFocus"] | null;
        };
        /**
         * TrackFocus
         * @description A checked retest waiting on this track: its next run uses the changed scenario for this gap.
         */
        TrackFocus: {
            /** Gap */
            gap: string;
            /** Lesson Title */
            lesson_title?: string | null;
            /** Session Id */
            session_id?: string | null;
            /** Evidence Seq */
            evidence_seq?: number[];
        };
        /** TurnInput */
        TurnInput: {
            /** Text */
            text: string;
            /** Step */
            step: number;
            /**
             * Board
             * @default false
             */
            board: boolean;
        };
        /** TurnRequest */
        TurnRequest: {
            /** Answer */
            answer: string;
        };
        /** TurnResponse */
        TurnResponse: {
            /** Answer Id */
            answer_id: string;
            /** Next Question */
            next_question: string;
            /**
             * Done
             * @description True on the turn that ends the interview part; the walkthrough follows.
             * @default false
             */
            done: boolean;
            /**
             * Degraded
             * @description True when the model failed and a planned question was used.
             * @default false
             */
            degraded: boolean;
            /**
             * Source
             * @description model | fallback | fake | scripted. Only 'model' was written by the live model.
             * @default model
             */
            source: string;
            /**
             * Ended Early
             * @description True when the patience meter ended the interview. The session is then in debrief.
             * @default false
             */
            ended_early: boolean;
            /** @description Null only when no real model is in use (fake provider). */
            meter?: components["schemas"]["MeterState"] | null;
        };
        /** TurnResult */
        TurnResult: {
            /** Events */
            events: components["schemas"]["Event"][];
            /** Source */
            source: string;
        };
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
            /** Input */
            input?: unknown;
            /** Context */
            ctx?: Record<string, never>;
        };
        /** WorkItem */
        WorkItem: {
            /** Id */
            id: string;
            /** Kind */
            kind: string;
            /** Subject Id */
            subject_id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
            /** Stage */
            stage: string;
            /** Result */
            result?: {
                [key: string]: unknown;
            } | null;
            /** Error */
            error?: string | null;
            /** Attempts */
            attempts: number;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Finished At */
            finished_at?: string | null;
        };
        /** Point */
        Point: {
            /** X */
            x: number;
            /** Y */
            y: number;
            /**
             * Pressure
             * @default 0.5
             */
            pressure: number;
        };
        /** Stroke */
        Stroke: {
            /** Id */
            id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "path" | "rect" | "arrow" | "text";
            /** Points */
            points: components["schemas"]["Point"][];
            /**
             * Label
             * @default
             */
            label: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    health_api_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    create_plan_api_plans_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PlanRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlanResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    start_session_api_sessions_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SessionStartRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionStartResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    take_turn_api_sessions__session_id__turns_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TurnRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TurnResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    probe_api_sessions__session_id__probe_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProbeRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProbeEvent"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    end_session_api_sessions__session_id__end_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EndSessionResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    session_events_api_sessions__session_id__events_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    report_api_sessions__session_id__report_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReportResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    debrief_api_sessions__session_id__debrief_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DebriefResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_session_api_sessions__session_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DeleteResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    skills_api_skills_get: {
        parameters: {
            query?: {
                user_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SkillsResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_lesson_api_lessons__skill_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                skill_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LessonResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_retest_api_retests_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RetestRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionStartResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    mastery_api_mastery_get: {
        parameters: {
            query: {
                user_id: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MasteryResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    metrics_api_metrics__session_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MetricsResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    socket_ticket_api_v2_sessions__sid__socket_ticket_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SocketTicketInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SocketTicket"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    account_export_api_v2_account_export_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    local_speech_start_api_v2_sessions__sid__local_speech_jobs_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LocalSpeechStart"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LocalSpeechJob"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    local_speech_finish_api_v2_sessions__sid__local_speech_jobs__jid__post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sid: string;
                jid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LocalSpeechFinish"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LocalSpeechJob"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    history_api_v2_history_get: {
        parameters: {
            query?: {
                before?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["History"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    health_api_v2_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Health"];
                };
            };
        };
    };
    plan_api_v2_plans_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Intake"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Plan"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    plan_job_api_v2_plans_jobs_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Intake"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkItem"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_plan_api_v2_plans__pid__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                pid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Plan"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    source_list_api_v2_users__user_id__sources_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourceList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    source_create_api_v2_sources_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SourceInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourceDocument"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    source_upload_api_v2_sources_upload_post: {
        parameters: {
            query: {
                user_id: string;
                kind?: "resume" | "repo" | "job_posting" | "notes" | "other";
                title: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourceDocument"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    source_github_api_v2_sources_github_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SourceLinkInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourceDocument"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    source_read_api_v2_sources__source_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                source_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourceDocument"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    source_extract_api_v2_sources__source_id__extract_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                source_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkItem"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    source_scan_api_v2_sources__source_id__scan_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                source_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkItem"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ats_read_api_v2_sources__source_id__ats_get: {
        parameters: {
            query?: {
                job_id?: string | null;
            };
            header?: never;
            path: {
                source_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AtsReview"] | null;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ats_start_api_v2_sources__source_id__ats_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                source_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AtsRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkItem"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ats_apply_api_v2_sources__source_id__ats_apply_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                source_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AtsApply"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourceDocument"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    source_pdf_api_v2_sources__source_id__pdf_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                source_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    source_confirm_api_v2_sources__source_id__confirm_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                source_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SourceConfirmation"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourceDocument"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    start_api_v2_sessions_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Start"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Session"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    session_api_v2_sessions__sid__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Session"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lab_action_api_v2_sessions__sid__lab_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LabAction"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TurnResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    pause_api_v2_sessions__sid__pause_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PauseInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Session"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    hint_api_v2_sessions__sid__hint_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Event"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    events_api_v2_sessions__sid__events_get: {
        parameters: {
            query?: {
                after?: number;
            };
            header?: never;
            path: {
                sid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Event"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    append_api_v2_sessions__sid__events_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EventInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Event"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    turn_api_v2_sessions__sid__turns_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TurnInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TurnResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reply_complete_api_v2_sessions__sid__reply_complete_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReplyAck"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    board_elements_api_v2_sessions__sid__board_elements_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BoardElementsInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Event"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    board_api_v2_sessions__sid__board_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BoardInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BoardResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    end_api_v2_sessions__sid__end_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Report"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    report_api_v2_sessions__sid__report_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Report"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    metrics_api_v2_sessions__sid__metrics_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Metrics"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lesson_api_v2_sessions__sid__lesson_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Lesson"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    generate_lesson_api_v2_sessions__sid__lesson_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Lesson"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lesson_job_api_v2_sessions__sid__lesson_jobs_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkItem"] | null;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    enqueue_lesson_api_v2_sessions__sid__lesson_jobs_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkItem"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_job_api_v2_jobs__jid__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                jid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkItem"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    retry_job_api_v2_jobs__jid__retry_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                jid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkItem"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    cancel_job_api_v2_jobs__jid__cancel_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                jid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkItem"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    retest_api_v2_retests_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RetestInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Session"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    pair_api_v2_sessions__sid__pair_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PairResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    artifact_api_v2_artifacts__aid__png_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                aid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    audio_api_v2_sessions__sid__audio_post: {
        parameters: {
            query?: {
                step?: number;
                board?: boolean;
            };
            header?: never;
            path: {
                sid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TurnResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    speech_api_v2_sessions__sid__speech__seq__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sid: string;
                seq: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    me_api_v2_auth_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuthState"];
                };
            };
        };
    };
    register_api_v2_auth_register_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Registration"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuthState"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    login_api_v2_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Credentials"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuthState"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    logout_api_v2_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuthState"];
                };
            };
        };
    };
}
