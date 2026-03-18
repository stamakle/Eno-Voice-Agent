class CourseTemplateSummary {
  CourseTemplateSummary({
    required this.courseId,
    required this.title,
    required this.levelBand,
  });

  final String courseId;
  final String title;
  final String levelBand;

  factory CourseTemplateSummary.fromJson(Map<String, dynamic> json) {
    return CourseTemplateSummary(
      courseId: json['course_id'] as String,
      title: json['title'] as String,
      levelBand: json['level_band'] as String,
    );
  }
}

class AuthUserModel {
  AuthUserModel({
    required this.userId,
    required this.learnerId,
    required this.email,
    required this.displayName,
    this.emailVerified = false,
  });

  final String userId;
  final String learnerId;
  final String email;
  final String displayName;
  final bool emailVerified;

  factory AuthUserModel.fromJson(Map<String, dynamic> json) {
    return AuthUserModel(
      userId: json['user_id'] as String? ?? '',
      learnerId: json['learner_id'] as String? ?? '',
      email: json['email'] as String? ?? '',
      displayName: json['display_name'] as String? ?? 'Learner',
      emailVerified: json['email_verified'] as bool? ?? false,
    );
  }
}

class AuthSessionModel {
  AuthSessionModel({
    required this.token,
    required this.refreshToken,
    required this.user,
    required this.expiresAt,
    required this.refreshExpiresAt,
    this.emailVerificationRequired = false,
    this.debugEmailVerificationToken,
  });

  final String token;
  final String refreshToken;
  final AuthUserModel user;
  final String expiresAt;
  final String refreshExpiresAt;
  final bool emailVerificationRequired;
  final String? debugEmailVerificationToken;

  factory AuthSessionModel.fromJson(Map<String, dynamic> json) {
    return AuthSessionModel(
      token: json['token'] as String? ?? '',
      refreshToken: json['refresh_token'] as String? ?? '',
      user: AuthUserModel.fromJson(json['user'] as Map<String, dynamic>? ?? <String, dynamic>{}),
      expiresAt: json['expires_at'] as String? ?? '',
      refreshExpiresAt: json['refresh_expires_at'] as String? ?? '',
      emailVerificationRequired: json['email_verification_required'] as bool? ?? false,
      debugEmailVerificationToken: json['debug_email_verification_token'] as String?,
    );
  }
}

class AuthMessageModel {
  AuthMessageModel({
    required this.status,
    required this.message,
    this.debugToken,
  });

  final String status;
  final String message;
  final String? debugToken;

  factory AuthMessageModel.fromJson(Map<String, dynamic> json) {
    return AuthMessageModel(
      status: json['status'] as String? ?? 'ok',
      message: json['message'] as String? ?? '',
      debugToken: json['debug_token'] as String?,
    );
  }
}

class AuthSessionSummaryModel {
  AuthSessionSummaryModel({
    required this.sessionId,
    required this.createdAt,
    required this.lastUsedAt,
    required this.expiresAt,
    required this.refreshExpiresAt,
    required this.current,
    this.revokedAt,
    this.ipAddress,
    this.userAgent,
  });

  final String sessionId;
  final String createdAt;
  final String lastUsedAt;
  final String expiresAt;
  final String refreshExpiresAt;
  final bool current;
  final String? revokedAt;
  final String? ipAddress;
  final String? userAgent;

  factory AuthSessionSummaryModel.fromJson(Map<String, dynamic> json) {
    return AuthSessionSummaryModel(
      sessionId: json['session_id'] as String? ?? '',
      createdAt: json['created_at'] as String? ?? '',
      lastUsedAt: json['last_used_at'] as String? ?? '',
      expiresAt: json['expires_at'] as String? ?? '',
      refreshExpiresAt: json['refresh_expires_at'] as String? ?? '',
      current: json['current'] as bool? ?? false,
      revokedAt: json['revoked_at'] as String?,
      ipAddress: json['ip_address'] as String?,
      userAgent: json['user_agent'] as String?,
    );
  }
}

class DashboardSummary {
  DashboardSummary({
    required this.displayName,
    required this.levelBand,
    required this.totalCompletedLessons,
    required this.weakTopics,
    required this.recommendedLesson,
    required this.nextLessonReason,
    required this.reviewCountDue,
    required this.nextReviewDueOn,
  });

  final String displayName;
  final String levelBand;
  final int totalCompletedLessons;
  final List<String> weakTopics;
  final NextLessonSelectionModel? recommendedLesson;
  final String? nextLessonReason;
  final int reviewCountDue;
  final String? nextReviewDueOn;

  factory DashboardSummary.fromJson(Map<String, dynamic> json) {
    final learner = json['learner'] as Map<String, dynamic>;
    final recommended = json['recommended_next_lesson'] as Map<String, dynamic>?;
    return DashboardSummary(
      displayName: learner['display_name'] as String? ?? 'Learner',
      levelBand: learner['level_band'] as String? ?? 'beginner',
      totalCompletedLessons: json['total_completed_lessons'] as int? ?? 0,
      weakTopics: (json['weak_topics'] as List<dynamic>? ?? []).cast<String>(),
      recommendedLesson:
          recommended == null ? null : NextLessonSelectionModel.fromJson(recommended),
      nextLessonReason: recommended?['reason'] as String?,
      reviewCountDue: json['review_count_due'] as int? ?? 0,
      nextReviewDueOn: json['next_review_due_on'] as String?,
    );
  }
}

class CoachClassificationModel {
  CoachClassificationModel({
    required this.levelBand,
    required this.levelLabel,
    required this.standing,
    required this.passStatus,
    required this.strengths,
    required this.weakAreas,
    required this.improvementFocus,
  });

  final String levelBand;
  final String levelLabel;
  final String standing;
  final String passStatus;
  final List<String> strengths;
  final List<String> weakAreas;
  final List<String> improvementFocus;

  factory CoachClassificationModel.fromJson(Map<String, dynamic> json) {
    return CoachClassificationModel(
      levelBand: json['level_band'] as String? ?? 'beginner',
      levelLabel: json['level_label'] as String? ?? 'beginner',
      standing: json['standing'] as String? ?? 'starting_out',
      passStatus: json['pass_status'] as String? ?? 'not_assessed',
      strengths: (json['strengths'] as List<dynamic>? ?? []).cast<String>(),
      weakAreas: (json['weak_areas'] as List<dynamic>? ?? []).cast<String>(),
      improvementFocus: (json['improvement_focus'] as List<dynamic>? ?? []).cast<String>(),
    );
  }
}

class CoachBootstrapModel {
  CoachBootstrapModel({
    required this.learnerId,
    required this.displayName,
    required this.levelBand,
    required this.levelLabel,
    required this.needsOnboarding,
    required this.hasResumeLesson,
    required this.totalCompletedLessons,
    required this.reviewCountDue,
    required this.weakTopics,
    required this.recommendedLesson,
    required this.recommendedLessonTitle,
    required this.spokenGreeting,
    required this.spokenProgressSummary,
    required this.spokenNextStep,
    required this.spokenResumeOffer,
    required this.classification,
    required this.preferredScenario,
  });

  final String learnerId;
  final String displayName;
  final String levelBand;
  final String levelLabel;
  final bool needsOnboarding;
  final bool hasResumeLesson;
  final int totalCompletedLessons;
  final int reviewCountDue;
  final List<String> weakTopics;
  final NextLessonSelectionModel? recommendedLesson;
  final String? recommendedLessonTitle;
  final String spokenGreeting;
  final String spokenProgressSummary;
  final String spokenNextStep;
  final String? spokenResumeOffer;
  final CoachClassificationModel classification;
  final String preferredScenario;

  factory CoachBootstrapModel.fromJson(Map<String, dynamic> json) {
    final recommended = json['recommended_next_lesson'] as Map<String, dynamic>?;
    return CoachBootstrapModel(
      learnerId: json['learner_id'] as String? ?? '',
      displayName: json['display_name'] as String? ?? 'Learner',
      levelBand: json['level_band'] as String? ?? 'beginner',
      levelLabel: json['level_label'] as String? ?? 'beginner',
      needsOnboarding: json['needs_onboarding'] as bool? ?? false,
      hasResumeLesson: json['has_resume_lesson'] as bool? ?? false,
      totalCompletedLessons: json['total_completed_lessons'] as int? ?? 0,
      reviewCountDue: json['review_count_due'] as int? ?? 0,
      weakTopics: (json['weak_topics'] as List<dynamic>? ?? []).cast<String>(),
      recommendedLesson: recommended == null ? null : NextLessonSelectionModel.fromJson(recommended),
      recommendedLessonTitle: json['recommended_lesson_title'] as String?,
      spokenGreeting: json['spoken_greeting'] as String? ?? '',
      spokenProgressSummary: json['spoken_progress_summary'] as String? ?? '',
      spokenNextStep: json['spoken_next_step'] as String? ?? '',
      spokenResumeOffer: json['spoken_resume_offer'] as String?,
      classification: CoachClassificationModel.fromJson(
        json['classification'] as Map<String, dynamic>? ?? <String, dynamic>{},
      ),
      preferredScenario: json['preferred_scenario'] as String? ?? 'General conversation',
    );
  }
}

class CoachTurnResponseModel {
  CoachTurnResponseModel({
    required this.handled,
    required this.spokenReply,
    required this.action,
    required this.lessonToOpen,
    required this.bootstrap,
  });

  final bool handled;
  final String spokenReply;
  final String action;
  final NextLessonSelectionModel? lessonToOpen;
  final CoachBootstrapModel bootstrap;

  factory CoachTurnResponseModel.fromJson(Map<String, dynamic> json) {
    final lessonToOpen = json['lesson_to_open'] as Map<String, dynamic>?;
    return CoachTurnResponseModel(
      handled: json['handled'] as bool? ?? true,
      spokenReply: json['spoken_reply'] as String? ?? '',
      action: json['action'] as String? ?? 'none',
      lessonToOpen: lessonToOpen == null ? null : NextLessonSelectionModel.fromJson(lessonToOpen),
      bootstrap: CoachBootstrapModel.fromJson(
        json['bootstrap'] as Map<String, dynamic>? ?? <String, dynamic>{},
      ),
    );
  }
}

class NextLessonSelectionModel {
  NextLessonSelectionModel({
    required this.courseId,
    required this.chapterId,
    required this.lessonId,
    required this.reason,
  });

  final String courseId;
  final String chapterId;
  final String lessonId;
  final String reason;

  factory NextLessonSelectionModel.fromJson(Map<String, dynamic> json) {
    return NextLessonSelectionModel(
      courseId: json['course_id'] as String,
      chapterId: json['chapter_id'] as String,
      lessonId: json['lesson_id'] as String,
      reason: json['reason'] as String,
    );
  }
}

class ExerciseModel {
  ExerciseModel({
    required this.exerciseId,
    required this.exerciseType,
    required this.prompt,
  });

  final String exerciseId;
  final String exerciseType;
  final String prompt;

  factory ExerciseModel.fromJson(Map<String, dynamic> json) {
    return ExerciseModel(
      exerciseId: json['exercise_id'] as String,
      exerciseType: json['exercise_type'] as String,
      prompt: json['prompt'] as String,
    );
  }
}

class SessionSnapshot {
  SessionSnapshot({
    required this.sessionId,
    required this.lessonTitle,
    required this.status,
    required this.variantId,
    required this.currentPrompt,
    required this.currentAttempt,
    required this.currentMaxAttempts,
    required this.pendingRetry,
    required this.completedExercises,
    required this.turnCount,
    required this.lessonSummary,
  });

  final String sessionId;
  final String lessonTitle;
  final String status;
  final String? variantId;
  final String? currentPrompt;
  final int currentAttempt;
  final int currentMaxAttempts;
  final bool pendingRetry;
  final List<String> completedExercises;
  final int turnCount;
  final String? lessonSummary;

  factory SessionSnapshot.fromJson(Map<String, dynamic> json) {
    return SessionSnapshot(
      sessionId: json['session_id'] as String,
      lessonTitle: json['lesson_title'] as String,
      status: json['status'] as String,
      variantId: json['variant_id'] as String?,
      currentPrompt: json['current_prompt'] as String?,
      currentAttempt: json['current_attempt'] as int? ?? 0,
      currentMaxAttempts: json['current_max_attempts'] as int? ?? 0,
      pendingRetry: json['pending_retry'] as bool? ?? false,
      completedExercises: (json['completed_exercises'] as List<dynamic>? ?? []).cast<String>(),
      turnCount: json['turn_count'] as int? ?? 0,
      lessonSummary: json['lesson_summary'] as String?,
    );
  }
}
