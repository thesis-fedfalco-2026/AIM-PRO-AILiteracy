// Generated from services/openapi/authoring.json by
// apps/packages/api-client/scripts/generate.mjs. Do not edit; run
// `npm run generate:client` in apps/ after the snapshot changes.

export interface paths {
    "/auth/callback": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Finish the code flow, map the identity and start a server-side session */
        get: operations["callback_auth_callback_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Start the OIDC code flow with PKCE at the identity provider */
        get: operations["login_auth_login_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** End the session; the result is the provider logout URL to visit, if any */
        post: operations["logout_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/session": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The signed-in subject and the CSRF token for writes */
        get: operations["session_auth_session_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Context summary with the same redaction as the CLI show */
        get: operations["context_summary_contexts__context_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}/aimpro-exports": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Upload an AIM-PRO project export: checked, then stored unchanged for a Curator job */
        post: operations["upload_contexts__context_id__aimpro_exports_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}/aimpro-exports/{sha256}/targets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The learning targets and practices of a stored export, with quotable texts */
        get: operations["read_targets_contexts__context_id__aimpro_exports__sha256__targets_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}/applications": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Apply an approved proposal; a replay of the operation id returns the same change */
        post: operations["apply_contexts__context_id__applications_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}/decisions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Record a human decision on the reviewed payload; 409 if its key or revision is stale */
        post: operations["decide_contexts__context_id__decisions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}/designs/{design_id}/versions/{version}/syllabus": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The approved syllabus of the current Curator outline (CLI show-aimpro-syllabus) */
        get: operations["design_syllabus_contexts__context_id__designs__design_id__versions__version__syllabus_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}/jobs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The jobs of a context, newest first, with their status */
        get: operations["listing_contexts__context_id__jobs_get"];
        put?: never;
        /** Queue an agent job; the same request id and command return the same job, another command 409 */
        post: operations["queue_contexts__context_id__jobs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}/jobs/{request_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** A job with its status and, once ended, its pending proposal or the reason it ended */
        get: operations["read_contexts__context_id__jobs__request_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}/jobs/{request_id}/abandonment": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Abandon a queued or interrupted job (administrators); 409 once the job has ended */
        post: operations["abandon_contexts__context_id__jobs__request_id__abandonment_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}/jobs/{request_id}/choice": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** The teacher's choice on prepared sources, once; only accepted sources ground a Curator job */
        post: operations["choose_contexts__context_id__jobs__request_id__choice_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}/jobs/{request_id}/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Server-sent events: status and content-free progress, until the job ends; resume with Last-Event-ID */
        get: operations["follow_contexts__context_id__jobs__request_id__events_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}/pending-proposals": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Proposals awaiting a decision; none for a learner-only subject, as in show */
        get: operations["pending_proposals_contexts__context_id__pending_proposals_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}/projects": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Propose a project from an approved syllabus (CLI init-authoring-project); a request id replays */
        post: operations["initialize_project_contexts__context_id__projects_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}/projects/{project_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Current selections, approval receipts and stale dependencies (CLI show-authoring-project) */
        get: operations["project_inspection_contexts__context_id__projects__project_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}/resources/{resource_id}/versions/{version}/project-syllabus": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The approved syllabus of this exact current project revision (CLI show-project-syllabus) */
        get: operations["project_syllabus_contexts__context_id__resources__resource_id__versions__version__project_syllabus_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}/resources/{resource_id}/versions/{version}/release": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Receipts, the exact frozen closure and findings of this release (CLI show-release) */
        get: operations["release_inspection_contexts__context_id__resources__resource_id__versions__version__release_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}/source-discoveries/{request_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The excerpts a discovery job found, to pick a source plan from */
        get: operations["discovery_contexts__context_id__source_discoveries__request_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}/source-preparations/{request_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The exact excerpts of a preparation job, for the teacher's choice */
        get: operations["preparation_contexts__context_id__source_preparations__request_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}/syllabus-edits": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Record a teacher's edit of a syllabus proposal as a new proposal by that teacher */
        post: operations["syllabus_edit_contexts__context_id__syllabus_edits_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}/syllabus-proposals/{proposal_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** A syllabus proposal in words, compared with the proposal it refines and the applied syllabus */
        get: operations["syllabus_proposal_contexts__context_id__syllabus_proposals__proposal_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/courses": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create a course: a new PREPARATION/DRAFT context with a new policy for its creator */
        post: operations["create_courses_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Liveness; needs no session */
        get: operations["health_health_get"];
        put?: never;
        post?: never;
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
        /**
         * AimproExport
         * @description An AIM-PRO project export in the worker's export directory, at this exact SHA-256.
         */
        AimproExport: {
            /** Name */
            name: string;
            /** Sha256 */
            sha256: string;
        };
        /**
         * ApplicationRequest
         * @description Apply an approved proposal, as the CLI ``apply``; ``operation_id`` makes a retry a replay.
         */
        ApplicationRequest: {
            /** Operation Id */
            operation_id: string;
            proposal: components["schemas"]["EntityRef"];
        };
        /** ApprovedSyllabus */
        ApprovedSyllabus: {
            artifact: components["schemas"]["SyllabusArtifact"];
            change: components["schemas"]["EntityRef"];
            decision: components["schemas"]["EntityRef"];
            proposal: components["schemas"]["EntityRef"];
            source: components["schemas"]["LeadInput"];
            syllabus: components["schemas"]["EntityRef"];
        };
        /** ArtifactInspection */
        ArtifactInspection: {
            /** Approval Error */
            approval_error?: string | null;
            receipt?: components["schemas"]["ReviewReceipt"] | null;
            selection: components["schemas"]["ArtifactSelection"];
        };
        /** ArtifactSelection */
        ArtifactSelection: {
            /**
             * Definitions
             * @default []
             */
            definitions: components["schemas"]["EntityRef"][];
            /**
             * Depends On
             * @default []
             */
            depends_on: components["schemas"]["EntityRef"][];
            /** Key */
            key: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "SOURCE" | "SYLLABUS" | "ASSESSMENT" | "TEACHER_CONTENT" | "TRAINER_CONTENT";
            resource: components["schemas"]["EntityRef"];
        };
        /**
         * AssessmentJob
         * @description The Evaluator: ``learning generate-project-assessments``.
         */
        "AssessmentJob-Input": {
            command: components["schemas"]["GenerationCommand-Input"];
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "generate-project-assessments";
        };
        /**
         * AssessmentJob
         * @description The Evaluator: ``learning generate-project-assessments``.
         */
        "AssessmentJob-Output": {
            command: components["schemas"]["GenerationCommand-Output"];
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "generate-project-assessments";
        };
        /**
         * CitedExcerpt
         * @description An excerpt a unit may cite; ``purpose`` and ``limitations`` exist for prepared sources only.
         */
        CitedExcerpt: {
            /** Document Id */
            document_id: string;
            /** Licence */
            licence: string;
            /** Limitations */
            limitations: string[];
            /** Purpose */
            purpose: string | null;
            /** Resource Id */
            resource_id: string;
            /** Resource Version */
            resource_version: string;
            /** Text */
            text: string;
            /** Title */
            title: string;
            /** Uri */
            uri: string;
        };
        /** Competency */
        Competency: {
            /** Description */
            description: string;
            /** Id */
            id: string;
            /** Name */
            name: string;
        };
        /**
         * ContextSummary
         * @description The context, the entities the subject may see and the snapshot findings.
         *
         *     A learner-only subject sees only the context, its own participant record and
         *     its own learning records, never proposals, decisions or other participants.
         */
        ContextSummary: {
            context: components["schemas"]["Entity"];
            /** Entities */
            entities: components["schemas"]["Entity"][];
            /** Findings */
            findings: components["schemas"]["Finding"][];
        };
        /** CorpusCitation */
        CorpusCitation: {
            /** Document Ids */
            document_ids: string[];
            /** Resource Id */
            resource_id: string;
            /** Resource Version */
            resource_version: string;
            /** Supported Claim */
            supported_claim: string;
        };
        /** CorpusDocument */
        CorpusDocument: {
            /** Id */
            id: string;
            /** Metadata */
            metadata: {
                [key: string]: unknown;
            };
            /** Score */
            score: number;
            /** Text */
            text: string;
        };
        /** CorpusEvidence */
        CorpusEvidence: {
            /** K */
            k: number;
            /** Query */
            query: string;
            /** Resources */
            resources: components["schemas"]["CorpusResource"][];
            selection?: components["schemas"]["SourceSelectionSummary"] | null;
            /** Source Scope */
            source_scope: string;
        };
        /** CorpusResource */
        CorpusResource: {
            /** Documents */
            documents: components["schemas"]["CorpusDocument"][];
            /** Identity */
            identity: string;
            /** Licence */
            licence: string;
            /** Source Scope */
            source_scope: string;
            /** Title */
            title: string;
            /** Uri */
            uri: string;
            /** Version */
            version: string;
        };
        /** CourseRequest */
        CourseRequest: {
            /**
             * Context Id
             * @description The new course id: lowercase letters, digits and hyphens
             */
            context_id: string;
        };
        /** CourseView */
        CourseView: {
            /** Context Id */
            context_id: string;
            policy_ref: components["schemas"]["EntityRef"];
        };
        /** CoverageRequirement */
        CoverageRequirement: {
            /**
             * Actor
             * @enum {string}
             */
            actor: "FACILITATOR" | "PEER" | "LEARNER";
            /**
             * Expected Intent
             * @enum {string}
             */
            expected_intent: "EXPLAIN" | "PRACTICE" | "ASSESS";
            /** Key */
            key: string;
            /** Required Action */
            required_action: string;
            /**
             * Source Field
             * @enum {string}
             */
            source_field: "description" | "inPractice" | "rationale" | "contextDetails";
            /** Source Object Id */
            source_object_id: string;
            /** Source Quote */
            source_quote: string;
            /** Source Target Id */
            source_target_id: string;
        };
        /**
         * DecisionRequest
         * @description A decision on ``target``, the exact revision the reviewer saw, as the CLI ``decide``.
         */
        DecisionRequest: {
            /**
             * Decision
             * @enum {string}
             */
            decision: "APPROVE" | "REJECT" | "REQUEST_REVISION";
            /** Reason */
            reason: string;
            /** Review Payload Key */
            review_payload_key: string;
            target: components["schemas"]["EntityRef"];
        };
        /** DiscoveredExcerpt */
        DiscoveredExcerpt: {
            /** Content Sha256 */
            content_sha256: string;
            /** Document Id */
            document_id: string;
            /** Found By */
            found_by: string[];
            /** Licence */
            licence: string;
            /** Licence Verdict */
            licence_verdict: string | null;
            /** Resource Id */
            resource_id: string;
            /** Resource Version */
            resource_version: string;
            /** Text */
            text: string;
            /** Title */
            title: string;
            /** Uri */
            uri: string;
        };
        /**
         * DiscoveryJob
         * @description Source discovery: ``learning discover-aimpro-syllabus-sources``; no model.
         */
        "DiscoveryJob-Input": {
            discovery: components["schemas"]["SourceDiscovery"];
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "discover-aimpro-syllabus-sources";
        };
        /**
         * DiscoveryJob
         * @description Source discovery: ``learning discover-aimpro-syllabus-sources``; no model.
         */
        "DiscoveryJob-Output": {
            discovery: components["schemas"]["SourceDiscovery"];
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "discover-aimpro-syllabus-sources";
        };
        /** EditedSyllabus */
        EditedSyllabus: {
            proposal: components["schemas"]["EntityRef"];
        };
        /** Entity */
        Entity: {
            /** Fields */
            fields: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            /** Id */
            id: string;
            provenance: components["schemas"]["Provenance"];
            /** Type */
            type: string;
            /** Version */
            version: string;
        };
        /** EntityRef */
        EntityRef: {
            /** Id */
            id: string;
            /** Type */
            type: string;
            /** Version */
            version: string;
        };
        /** ErrorBody */
        ErrorBody: {
            /** Detail */
            detail: string | components["schemas"]["ValidationIssue"][];
            /** Error */
            error: string;
            /** Request Id */
            request_id: string;
        };
        /**
         * ExportObject
         * @description An object of the export with the texts a coverage requirement may quote.
         */
        ExportObject: {
            /** Class Name */
            class_name: string;
            /** Fields */
            fields: {
                [key: string]: string;
            };
            /** Id */
            id: string;
        };
        /**
         * ExportReport
         * @description An accepted export: its name and digest for a Curator job, and what the scenario check found.
         */
        ExportReport: {
            /** Competencies */
            competencies: string;
            /** Conforms */
            conforms: boolean;
            /** Contract Findings */
            contract_findings: {
                [key: string]: components["schemas"]["JsonValue"];
            }[];
            export: components["schemas"]["AimproExport"];
            /** Objects */
            objects: number;
            /** Project Id */
            project_id: string;
            /** Root Id */
            root_id: string;
            /** Scenario */
            scenario: string;
            /** Size */
            size: number;
            /** Source Diagnostics */
            source_diagnostics: {
                [key: string]: components["schemas"]["JsonValue"];
            }[];
        };
        /**
         * ExportTarget
         * @description A learning target with its practices: the anchors of a coverage requirement.
         */
        ExportTarget: {
            /** Class Name */
            class_name: string;
            /** Fields */
            fields: {
                [key: string]: string;
            };
            /** Id */
            id: string;
            /** Practices */
            practices: components["schemas"]["ExportObject"][];
        };
        /**
         * ExportTargets
         * @description The learning targets of a stored export's scenario, for the coverage requirements of a source plan.
         */
        ExportTargets: {
            /** Competencies */
            competencies: string;
            export: components["schemas"]["AimproExport"];
            /** Root Id */
            root_id: string;
            /** Scenario */
            scenario: string;
            /** Targets */
            targets: components["schemas"]["ExportTarget"][];
        };
        /** Finding */
        Finding: {
            /** Code */
            code: string;
            /** Reason */
            reason: string;
            /**
             * Resolution
             * @default Correct the data or provide the required configuration.
             */
            resolution: string;
            /**
             * Severity
             * @default BLOCKING
             * @enum {string}
             */
            severity: "BLOCKING" | "WARNING" | "INFORMATION";
            /** Target */
            target: string;
        };
        /** GenerationCommand */
        "GenerationCommand-Input": {
            /**
             * Assessments
             * @default []
             */
            assessments: components["schemas"]["EntityRef"][];
            base_context: components["schemas"]["EntityRef"];
            project: components["schemas"]["EntityRef"];
            /**
             * Requirements
             * @default []
             */
            requirements: string[];
            /**
             * Shared Content
             * @default []
             */
            shared_content: components["schemas"]["EntityRef"][];
            /**
             * Stimulus Requirements
             * @default []
             */
            stimulus_requirements: components["schemas"]["StimulusRequirement"][];
            teacher_plan?: components["schemas"]["TeacherPlan-Input"] | null;
        };
        /** GenerationCommand */
        "GenerationCommand-Output": {
            /**
             * Assessments
             * @default []
             */
            assessments: components["schemas"]["EntityRef"][];
            base_context: components["schemas"]["EntityRef"];
            project: components["schemas"]["EntityRef"];
            /**
             * Requirements
             * @default []
             */
            requirements: string[];
            /**
             * Shared Content
             * @default []
             */
            shared_content: components["schemas"]["EntityRef"][];
            /**
             * Stimulus Requirements
             * @default []
             */
            stimulus_requirements: components["schemas"]["StimulusRequirement"][];
            teacher_plan?: components["schemas"]["TeacherPlan-Output"] | null;
        };
        /** HealthView */
        HealthView: {
            /**
             * Status
             * @constant
             */
            status: "ok";
        };
        /**
         * JobList
         * @description The jobs of a context, newest first.
         */
        JobList: {
            /** Jobs */
            jobs: components["schemas"]["JobView"][];
        };
        /**
         * JobRequest
         * @description A job command with the client's ``request_id``, the ALM idempotency key.
         */
        JobRequest: {
            /** Job */
            job: components["schemas"]["AssessmentJob-Input"] | components["schemas"]["TeacherJob-Input"] | components["schemas"]["TrainerJob-Input"] | components["schemas"]["SyllabusJob"] | components["schemas"]["RevisionJob"] | components["schemas"]["DiscoveryJob-Input"] | components["schemas"]["PreparationJob-Input"];
            /** Request Id */
            request_id: string;
        };
        /**
         * JobView
         * @description A job: its exact command, its status and, once ended, its pending proposal or the reason it ended.
         */
        JobView: {
            /** Context Id */
            context_id: string;
            /** Created */
            created: string;
            /** Detail */
            detail?: string | null;
            /** Job */
            job: components["schemas"]["AssessmentJob-Output"] | components["schemas"]["TeacherJob-Output"] | components["schemas"]["TrainerJob-Output"] | components["schemas"]["SyllabusJob"] | components["schemas"]["RevisionJob"] | components["schemas"]["DiscoveryJob-Output"] | components["schemas"]["PreparationJob-Output"];
            /** Proposal Refs */
            proposal_refs: components["schemas"]["EntityRef"][];
            /** Request Id */
            request_id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "QUEUED" | "RUNNING" | "PROPOSED" | "REJECTED" | "FAILED" | "ABANDONED" | "COMPLETED" | "AWAITING_CHOICE" | "ACCEPTED" | "DECLINED";
            /** Subject Key */
            subject_key: string;
            /** Updated */
            updated: string;
        };
        JsonValue: unknown;
        /** LeadInput */
        LeadInput: {
            /** Conforms To Generated Contracts */
            conforms_to_generated_contracts: boolean;
            corpus_evidence?: components["schemas"]["CorpusEvidence"] | null;
            /** Domain Schemas */
            domain_schemas: {
                [key: string]: {
                    [key: string]: unknown;
                };
            };
            /** Findings */
            findings: {
                [key: string]: unknown;
            }[];
            /** Metamodel Fingerprint */
            metamodel_fingerprint: string;
            /**
             * Purpose
             * @default AUTHORING_REVIEW
             * @constant
             */
            purpose: "AUTHORING_REVIEW";
            source: components["schemas"]["ScenarioInput"];
            /** Transport Conversions */
            transport_conversions: {
                [key: string]: unknown;
            }[];
            /** Validated Objects */
            validated_objects: {
                [key: string]: unknown;
            }[];
        };
        /** LogoutView */
        LogoutView: {
            /** End Session Url */
            end_session_url: string | null;
        };
        /** PendingProposal */
        PendingProposal: {
            /** Candidates */
            candidates: components["schemas"]["Entity"][];
            proposal: components["schemas"]["Entity"];
            /** Review Payload Key */
            review_payload_key: string;
        };
        /**
         * PendingProposals
         * @description Newest first. A decision must carry the ``review_payload_key`` of the payload the reviewer saw.
         */
        PendingProposals: {
            /** Proposals */
            proposals: components["schemas"]["PendingProposal"][];
        };
        /** Practice */
        Practice: {
            /** Id */
            id: string;
            /** Name */
            name: string;
            /** Text */
            text: string;
        };
        /**
         * PreparationJob
         * @description Source preparation: ``learning prepare-aimpro-syllabus-sources``; no model. Awaits the teacher's choice.
         */
        "PreparationJob-Input": {
            /**
             * Competencies
             * @default elena_usecase_competencies
             */
            competencies: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "prepare-aimpro-syllabus-sources";
            plan: components["schemas"]["SourcePlan"];
            project: components["schemas"]["AimproExport"];
            /** Root Id */
            root_id?: string | null;
            /**
             * Scenario
             * @default SCN01
             */
            scenario: string;
        };
        /**
         * PreparationJob
         * @description Source preparation: ``learning prepare-aimpro-syllabus-sources``; no model. Awaits the teacher's choice.
         */
        "PreparationJob-Output": {
            /**
             * Competencies
             * @default elena_usecase_competencies
             */
            competencies: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "prepare-aimpro-syllabus-sources";
            plan: components["schemas"]["SourcePlan"];
            project: components["schemas"]["AimproExport"];
            /** Root Id */
            root_id?: string | null;
            /**
             * Scenario
             * @default SCN01
             */
            scenario: string;
        };
        /** PreparedExcerpt */
        PreparedExcerpt: {
            /** Content Sha256 */
            content_sha256: string;
            /** Document Id */
            document_id: string;
            /** Licence */
            licence: string;
            /** Licence Verdict */
            licence_verdict: string | null;
            /** Limitations */
            limitations: string[];
            /** Purpose */
            purpose: string;
            /** Resource Id */
            resource_id: string;
            /** Resource Version */
            resource_version: string;
            /** Text */
            text: string;
            /** Title */
            title: string;
            /** Uri */
            uri: string;
        };
        /**
         * ProjectInitializationRequest
         * @description ``init-authoring-project``: the exact approved syllabus and base context, with the ALM request id.
         */
        ProjectInitializationRequest: {
            base_context: components["schemas"]["EntityRef"];
            /** Project Id */
            project_id: string;
            /** Request Id */
            request_id: string;
            syllabus: components["schemas"]["EntityRef"];
        };
        /** ProjectInspection */
        ProjectInspection: {
            /** Approval Error */
            approval_error?: string | null;
            /** Artifacts */
            artifacts: components["schemas"]["ArtifactInspection"][];
            manifest: components["schemas"]["ProjectManifest"];
            project: components["schemas"]["EntityRef"];
            receipt?: components["schemas"]["ReviewReceipt"] | null;
            /** Stale Dependencies */
            stale_dependencies: components["schemas"]["Finding"][];
        };
        /** ProjectManifest */
        ProjectManifest: {
            /** Artifacts */
            artifacts: components["schemas"]["ArtifactSelection"][];
            /** Authoring Context */
            authoring_context: string;
            design: components["schemas"]["EntityRef"];
            /**
             * Format
             * @default authoring-project
             * @constant
             */
            format: "authoring-project";
            /**
             * Format Version
             * @default 1
             * @constant
             */
            format_version: 1;
            previous?: components["schemas"]["EntityRef"] | null;
            /** Project Id */
            project_id: string;
            /** Required Kinds */
            required_kinds: ("SOURCE" | "SYLLABUS" | "ASSESSMENT" | "TEACHER_CONTENT" | "TRAINER_CONTENT")[];
        };
        /** ProjectProposal */
        ProjectProposal: {
            design: components["schemas"]["EntityRef"];
            domain: components["schemas"]["EntityRef"];
            project: components["schemas"]["EntityRef"];
            proposal: components["schemas"]["EntityRef"];
        };
        /** ProtectedCaseFact */
        ProtectedCaseFact: {
            assessment: components["schemas"]["EntityRef"];
            /** Quote */
            quote: string;
            /** Stimulus Key */
            stimulus_key: string;
            /** Unit Key */
            unit_key: string;
        };
        /** Provenance */
        Provenance: {
            /**
             * Origin
             * @enum {string}
             */
            origin: "CONFIGURATION" | "GENERATED_PROPOSAL" | "INITIAL_CONTEXT" | "HUMAN_DECISION" | "OBSERVED_EVENT" | "UNRESOLVED_GAP";
            /** Rationale */
            rationale?: string | null;
            /** Responsible */
            responsible: string;
            /** Sources */
            sources?: string[];
        };
        /** ReleasedArtifact */
        ReleasedArtifact: {
            receipt?: components["schemas"]["ReviewReceipt"] | null;
            resource: components["schemas"]["EntityRef"];
        };
        /** ReleaseInspection */
        ReleaseInspection: {
            /** Artifacts */
            artifacts: components["schemas"]["ReleasedArtifact"][];
            /** Closure */
            closure: components["schemas"]["EntityRef"][];
            /** Findings */
            findings: components["schemas"]["Finding"][];
            manifest: components["schemas"]["ReleaseManifest"];
            project_receipt?: components["schemas"]["ReviewReceipt"] | null;
            receipt?: components["schemas"]["ReviewReceipt"] | null;
            release: components["schemas"]["EntityRef"];
        };
        /** ReleaseManifest */
        ReleaseManifest: {
            /** Artifacts */
            artifacts: components["schemas"]["EntityRef"][];
            /** Authoring Context */
            authoring_context: string;
            design: components["schemas"]["EntityRef"];
            domain: components["schemas"]["EntityRef"];
            /**
             * Format
             * @default authoring-release
             * @constant
             */
            format: "authoring-release";
            /**
             * Format Version
             * @default 1
             * @constant
             */
            format_version: 1;
            project: components["schemas"]["EntityRef"];
        };
        /** ReviewReceipt */
        ReviewReceipt: {
            change: components["schemas"]["EntityRef"];
            decision: components["schemas"]["EntityRef"];
            proposal: components["schemas"]["EntityRef"];
        };
        /**
         * RevisionJob
         * @description The Curator's revision: ``learning revise-aimpro-syllabus``, after a revision request on the proposal.
         */
        RevisionJob: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "revise-aimpro-syllabus";
            /**
             * Proposal
             * @description Syllabus proposal id, whose latest revision holds the revision request
             */
            proposal: string;
        };
        /** ScenarioInput */
        ScenarioInput: {
            /** Competency Ids */
            competency_ids: string[];
            /** Diagnostics */
            diagnostics: {
                [key: string]: unknown;
            }[];
            /** Excluded Scenario Object Ids */
            excluded_scenario_object_ids: string[];
            /** Limitations */
            limitations: string[];
            /** Objects */
            objects: components["schemas"]["SourceObject"][];
            /** Project Id */
            project_id: string;
            /**
             * Purpose
             * @default AUTHORING_REVIEW
             * @constant
             */
            purpose: "AUTHORING_REVIEW";
            /** Root Id */
            root_id: string;
            /** Scenario Model Id */
            scenario_model_id: string;
            /** Source Sha256 */
            source_sha256: string;
        };
        /** SelectedExcerpt */
        SelectedExcerpt: {
            /** Content Sha256 */
            content_sha256: string;
            /** Document Id */
            document_id: string;
            /** Limitations */
            limitations: string[];
            /** Purpose */
            purpose: string;
            /** Resource Id */
            resource_id: string;
            /** Resource Version */
            resource_version: string;
        };
        /** SessionView */
        SessionView: {
            /** Csrf Token */
            csrf_token: string;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /** Subject Key */
            subject_key: string;
        };
        /**
         * SourceChoice
         * @description The teacher's choice on prepared sources: only accepted sources ground a Curator job.
         */
        SourceChoice: {
            /**
             * Choice
             * @enum {string}
             */
            choice: "ACCEPTED" | "DECLINED";
        };
        /**
         * SourceDiscovery
         * @description The queries a teacher runs to find excerpts for a source plan; no excerpt is selected yet.
         */
        SourceDiscovery: {
            /**
             * Format
             * @default aimpro-source-discovery
             * @constant
             */
            format: "aimpro-source-discovery";
            /**
             * Format Version
             * @default 1
             * @constant
             */
            format_version: 1;
            /** Queries */
            queries: components["schemas"]["SourceQuery"][];
            /** Source Scope */
            source_scope: string;
        };
        /**
         * SourceDiscoveryView
         * @description The excerpts the discovery queries found, each once, in the order they were found.
         */
        SourceDiscoveryView: {
            /** Duplicate Hits */
            duplicate_hits: number;
            /** Excerpts */
            excerpts: components["schemas"]["DiscoveredExcerpt"][];
            /** Queries */
            queries: components["schemas"]["SourceQuery"][];
            /** Request Id */
            request_id: string;
            /** Source Scope */
            source_scope: string;
            /** Unique Documents */
            unique_documents: number;
        };
        /**
         * SourceObject
         * @description Transport envelope, not a generated AIM-PRO domain class.
         */
        SourceObject: {
            /** Attributes */
            attributes: {
                [key: string]: unknown;
            };
            /** Children */
            children: {
                [key: string]: string[];
            };
            /** Class Name */
            class_name: string;
            /** Id */
            id: string;
            /** Metamodel Id */
            metamodel_id: string;
            /** Model Id */
            model_id: string;
            /** Name */
            name?: string | null;
            /** Package */
            package: string;
            /** References */
            references: {
                [key: string]: string[];
            };
        };
        /** SourcePlan */
        SourcePlan: {
            /**
             * Coverage Requirements
             * @default []
             */
            coverage_requirements: components["schemas"]["CoverageRequirement"][];
            /** Documents */
            documents: components["schemas"]["SelectedExcerpt"][];
            /**
             * Format
             * @default aimpro-source-plan
             * @constant
             */
            format: "aimpro-source-plan";
            /**
             * Format Version
             * @default 1
             * @constant
             */
            format_version: 1;
            /**
             * Max Documents Per Resource
             * @default 4
             */
            max_documents_per_resource: number;
            /**
             * Min Resources
             * @default 1
             */
            min_resources: number;
            /** Queries */
            queries: components["schemas"]["SourceQuery"][];
            /** Source Scope */
            source_scope: string;
            /** Source Sha256 */
            source_sha256: string;
        };
        /**
         * SourcePreparationView
         * @description The exact excerpts of a preparation, for the teacher's choice, and the plan they were prepared from.
         */
        SourcePreparationView: {
            /** Coverage Requirements */
            coverage_requirements: components["schemas"]["CoverageRequirement"][];
            /** Duplicate Hits */
            duplicate_hits: number;
            /** Excerpts */
            excerpts: components["schemas"]["PreparedExcerpt"][];
            /** Max Documents Per Resource */
            max_documents_per_resource: number;
            /** Min Resources */
            min_resources: number;
            /** Queries */
            queries: components["schemas"]["SourceQuery"][];
            /** Request Id */
            request_id: string;
            /** Source Scope */
            source_scope: string;
            /** Source Sha256 */
            source_sha256: string;
            /** Unique Documents */
            unique_documents: number;
        };
        /** SourceQuery */
        SourceQuery: {
            /**
             * K
             * @default 20
             */
            k: number;
            /** Query */
            query: string;
        };
        /** SourceSelectionSummary */
        SourceSelectionSummary: {
            /**
             * Coverage Requirements
             * @default []
             */
            coverage_requirements: components["schemas"]["CoverageRequirement"][];
            /** Documents */
            documents: components["schemas"]["SelectedExcerpt"][];
            /** Queries */
            queries: components["schemas"]["SourceQuery"][];
            /** Trace Sha256 */
            trace_sha256: string;
        };
        /** StimulusRequirement */
        StimulusRequirement: {
            /** Brief */
            brief: string;
            /** Key */
            key: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "PROMPT_VARIANT" | "PEER_FAILURE" | "PROMPT_MOVE_CARD" | "TRANSCRIPT" | "OTHER";
            /** Unit Key */
            unit_key: string;
        };
        /** SyllabusArtifact */
        SyllabusArtifact: {
            /** Context Id */
            context_id: string;
            /**
             * Curator
             * @default syllabus-designer
             * @constant
             */
            curator: "syllabus-designer";
            draft: components["schemas"]["SyllabusDraft-Output"];
            /** Edited By */
            edited_by?: string | null;
            /**
             * Format
             * @default aimpro-syllabus
             * @constant
             */
            format: "aimpro-syllabus";
            /**
             * Format Version
             * @default 1
             * @constant
             */
            format_version: 1;
            outline: components["schemas"]["EntityRef"];
            review?: components["schemas"]["SyllabusVerdict"] | null;
            revises?: components["schemas"]["EntityRef"] | null;
            /**
             * Revision Reasons
             * @default []
             */
            revision_reasons: string[];
            source_snapshot: components["schemas"]["EntityRef"];
            /** Units */
            units: components["schemas"]["UnitLink"][];
        };
        /**
         * SyllabusComparison
         * @description ``units`` follows the order of the later syllabus; a removed unit follows the last unit of its target.
         */
        SyllabusComparison: {
            /** Gaps Added */
            gaps_added: string[];
            /** Gaps Removed */
            gaps_removed: string[];
            /** Order Changed */
            order_changed: boolean;
            /** Title Changed */
            title_changed: boolean;
            /** Units */
            units: components["schemas"]["UnitComparison"][];
        };
        /** SyllabusDraft */
        "SyllabusDraft-Input": {
            /**
             * Gaps
             * @default []
             */
            gaps: string[];
            /**
             * Kind
             * @default SYLLABUS_DRAFT
             * @constant
             */
            kind: "SYLLABUS_DRAFT";
            /** Metamodel Fingerprint */
            metamodel_fingerprint: string;
            /** Source Sha256 */
            source_sha256: string;
            /** Title */
            title: string;
            /** Units */
            units: components["schemas"]["SyllabusUnit"][];
        };
        /** SyllabusDraft */
        "SyllabusDraft-Output": {
            /**
             * Gaps
             * @default []
             */
            gaps: string[];
            /**
             * Kind
             * @default SYLLABUS_DRAFT
             * @constant
             */
            kind: "SYLLABUS_DRAFT";
            /** Metamodel Fingerprint */
            metamodel_fingerprint: string;
            /** Source Sha256 */
            source_sha256: string;
            /** Title */
            title: string;
            /** Units */
            units: components["schemas"]["SyllabusUnit"][];
        };
        /**
         * SyllabusEdit
         * @description The teacher's whole syllabus in place of ``proposal`` (an id); ``request_id`` makes a retry a replay.
         */
        SyllabusEdit: {
            draft: components["schemas"]["SyllabusDraft-Input"];
            /** Proposal */
            proposal: string;
            /** Request Id */
            request_id: string;
        };
        /**
         * SyllabusJob
         * @description The Curator: ``learning generate-aimpro-syllabus``, grounded by a query or prepared sources.
         */
        SyllabusJob: {
            /**
             * Competencies
             * @default elena_usecase_competencies
             */
            competencies: string;
            /**
             * K
             * @default 5
             */
            k: number;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "generate-aimpro-syllabus";
            /**
             * Prepared Sources
             * @description Exact completed source-preparation request id
             */
            prepared_sources?: string | null;
            project: components["schemas"]["AimproExport"];
            /** Query */
            query?: string | null;
            /** Root Id */
            root_id?: string | null;
            /**
             * Scenario
             * @default SCN01
             */
            scenario: string;
            /** Source Scope */
            source_scope: string;
        };
        /**
         * SyllabusProposalView
         * @description The syllabus of a proposal, the one it refines and the course's applied syllabus, with their texts.
         */
        SyllabusProposalView: {
            compared_with_current: components["schemas"]["SyllabusComparison"];
            compared_with_refined: components["schemas"]["SyllabusComparison"] | null;
            /**
             * Course Design
             * @default NONE
             * @enum {string}
             */
            course_design: "NONE" | "SYLLABUS" | "OTHER";
            current: components["schemas"]["SyllabusRecord"] | null;
            /** Excerpts */
            excerpts: components["schemas"]["CitedExcerpt"][];
            refined: components["schemas"]["SyllabusRecord"] | null;
            syllabus: components["schemas"]["SyllabusRecord"];
            /** Targets */
            targets: components["schemas"]["Target"][];
        };
        /** SyllabusRecord */
        SyllabusRecord: {
            draft: components["schemas"]["SyllabusDraft-Output"];
            /** Edited By */
            edited_by: string | null;
            proposal: components["schemas"]["EntityRef"];
            /** Responsible */
            responsible: string;
            review: components["schemas"]["SyllabusVerdict"] | null;
            /** Reviewed By Agent */
            reviewed_by_agent: boolean;
            /** Revision Reasons */
            revision_reasons: string[];
            /** Status */
            status: string;
        };
        /** SyllabusUnit */
        SyllabusUnit: {
            /** Corpus Citations */
            corpus_citations: components["schemas"]["CorpusCitation"][];
            /**
             * Coverage
             * @default []
             */
            coverage: components["schemas"]["UnitCoverage"][];
            /** Key */
            key: string;
            /** Planned Intents */
            planned_intents: ("EXPLAIN" | "PRACTICE" | "ASSESS")[];
            /** Purpose */
            purpose: string;
            /** Source Competency Ids */
            source_competency_ids: string[];
            /** Source Practice Ids */
            source_practice_ids: string[];
            /** Source Target Id */
            source_target_id: string;
            /** Title */
            title: string;
        };
        /** SyllabusVerdict */
        SyllabusVerdict: {
            /** Citation Support */
            citation_support: boolean;
            /** Reason */
            reason: string;
            /** Source Alignment */
            source_alignment: boolean;
            /**
             * Verdict
             * @enum {string}
             */
            verdict: "ACCEPT" | "REJECT" | "UNCERTAIN";
        };
        /** Target */
        Target: {
            /** Competencies */
            competencies: components["schemas"]["Competency"][];
            /** Id */
            id: string;
            /** Practices */
            practices: components["schemas"]["Practice"][];
            /** Statement */
            statement: string;
        };
        /**
         * TeacherJob
         * @description The Teacher: ``learning generate-project-teacher``.
         */
        "TeacherJob-Input": {
            command: components["schemas"]["GenerationCommand-Input"];
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "generate-project-teacher";
        };
        /**
         * TeacherJob
         * @description The Teacher: ``learning generate-project-teacher``.
         */
        "TeacherJob-Output": {
            command: components["schemas"]["GenerationCommand-Output"];
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "generate-project-teacher";
        };
        /** TeacherPlan */
        "TeacherPlan-Input": {
            /**
             * Format Version
             * @default 1
             * @constant
             */
            format_version: 1;
            /**
             * Protected Case Facts
             * @default []
             */
            protected_case_facts: components["schemas"]["ProtectedCaseFact"][];
            /**
             * Transcript Peers
             * @default []
             */
            transcript_peers: components["schemas"]["TranscriptPeerLink"][];
        };
        /** TeacherPlan */
        "TeacherPlan-Output": {
            /**
             * Format Version
             * @default 1
             * @constant
             */
            format_version: 1;
            /**
             * Protected Case Facts
             * @default []
             */
            protected_case_facts: components["schemas"]["ProtectedCaseFact"][];
            /**
             * Transcript Peers
             * @default []
             */
            transcript_peers: components["schemas"]["TranscriptPeerLink"][];
        };
        /**
         * TrainerJob
         * @description The Trainer: ``learning generate-project-trainer``.
         */
        "TrainerJob-Input": {
            command: components["schemas"]["GenerationCommand-Input"];
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "generate-project-trainer";
        };
        /**
         * TrainerJob
         * @description The Trainer: ``learning generate-project-trainer``.
         */
        "TrainerJob-Output": {
            command: components["schemas"]["GenerationCommand-Output"];
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "generate-project-trainer";
        };
        /** TranscriptPeerLink */
        TranscriptPeerLink: {
            /** Peer Key */
            peer_key: string;
            /** Transcript Key */
            transcript_key: string;
        };
        /** UnitComparison */
        UnitComparison: {
            after: components["schemas"]["SyllabusUnit"] | null;
            before: components["schemas"]["SyllabusUnit"] | null;
            /**
             * Changed Fields
             * @default []
             */
            changed_fields: ("title" | "purpose" | "planned_intents" | "source_competency_ids" | "source_practice_ids" | "corpus_citations" | "coverage")[];
            /**
             * Status
             * @enum {string}
             */
            status: "ADDED" | "REMOVED" | "CHANGED" | "UNCHANGED";
            /** Target Id */
            target_id: string;
        };
        /** UnitCoverage */
        UnitCoverage: {
            /** Planned Action */
            planned_action: string;
            /** Requirement Key */
            requirement_key: string;
        };
        /** UnitLink */
        UnitLink: {
            /** Key */
            key: string;
            node: components["schemas"]["EntityRef"];
        };
        /** ValidationIssue */
        ValidationIssue: {
            /** Loc */
            loc: (string | number)[];
            /** Msg */
            msg: string;
            /** Type */
            type: string;
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
    callback_auth_callback_get: {
        parameters: {
            query?: {
                code?: string | null;
                error?: string | null;
                state?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            303: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Identity provider unavailable */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    login_auth_login_get: {
        parameters: {
            query?: {
                /** @description Local path to return to */
                return_to?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            302: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Identity provider unavailable */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    logout_auth_logout_post: {
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
                    "application/json": components["schemas"]["LogoutView"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    session_auth_session_get: {
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
                    "application/json": components["schemas"]["SessionView"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    context_summary_contexts__context_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                context_id: string;
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
                    "application/json": components["schemas"]["ContextSummary"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    upload_contexts__context_id__aimpro_exports_post: {
        parameters: {
            query?: {
                competencies?: string;
                root_id?: string | null;
                scenario?: string;
            };
            header?: never;
            path: {
                context_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/octet-stream": string;
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExportReport"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    read_targets_contexts__context_id__aimpro_exports__sha256__targets_get: {
        parameters: {
            query?: {
                competencies?: string;
                root_id?: string | null;
                scenario?: string;
            };
            header?: never;
            path: {
                context_id: string;
                sha256: string;
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
                    "application/json": components["schemas"]["ExportTargets"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    apply_contexts__context_id__applications_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                context_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ApplicationRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Entity"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    decide_contexts__context_id__decisions_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                context_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DecisionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Entity"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    design_syllabus_contexts__context_id__designs__design_id__versions__version__syllabus_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                context_id: string;
                design_id: string;
                version: string;
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
                    "application/json": components["schemas"]["ApprovedSyllabus"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    listing_contexts__context_id__jobs_get: {
        parameters: {
            query?: {
                limit?: number;
            };
            header?: never;
            path: {
                context_id: string;
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
                    "application/json": components["schemas"]["JobList"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    queue_contexts__context_id__jobs_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                context_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["JobRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JobView"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    read_contexts__context_id__jobs__request_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                context_id: string;
                request_id: string;
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
                    "application/json": components["schemas"]["JobView"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    abandon_contexts__context_id__jobs__request_id__abandonment_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                context_id: string;
                request_id: string;
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
                    "application/json": components["schemas"]["JobView"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    choose_contexts__context_id__jobs__request_id__choice_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                context_id: string;
                request_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SourceChoice"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JobView"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    follow_contexts__context_id__jobs__request_id__events_get: {
        parameters: {
            query?: never;
            header?: {
                "Last-Event-ID"?: string | null;
            };
            path: {
                context_id: string;
                request_id: string;
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
                    "text/event-stream": unknown;
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    pending_proposals_contexts__context_id__pending_proposals_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                context_id: string;
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
                    "application/json": components["schemas"]["PendingProposals"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    initialize_project_contexts__context_id__projects_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                context_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProjectInitializationRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectProposal"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    project_inspection_contexts__context_id__projects__project_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                context_id: string;
                project_id: string;
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
                    "application/json": components["schemas"]["ProjectInspection"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    project_syllabus_contexts__context_id__resources__resource_id__versions__version__project_syllabus_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                context_id: string;
                resource_id: string;
                version: string;
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
                    "application/json": components["schemas"]["ApprovedSyllabus"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    release_inspection_contexts__context_id__resources__resource_id__versions__version__release_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                context_id: string;
                resource_id: string;
                version: string;
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
                    "application/json": components["schemas"]["ReleaseInspection"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    discovery_contexts__context_id__source_discoveries__request_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                context_id: string;
                request_id: string;
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
                    "application/json": components["schemas"]["SourceDiscoveryView"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    preparation_contexts__context_id__source_preparations__request_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                context_id: string;
                request_id: string;
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
                    "application/json": components["schemas"]["SourcePreparationView"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    syllabus_edit_contexts__context_id__syllabus_edits_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                context_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SyllabusEdit"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EditedSyllabus"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    syllabus_proposal_contexts__context_id__syllabus_proposals__proposal_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                context_id: string;
                proposal_id: string;
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
                    "application/json": components["schemas"]["SyllabusProposalView"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    create_courses_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CourseRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CourseView"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    health_health_get: {
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
                    "application/json": components["schemas"]["HealthView"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
}
