import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

import '../config/app_config.dart';
import '../services/api_client.dart';
import '../state/app_state.dart';
import '../theme/aura_theme.dart';
import '../widgets/google_sign_in_web_button.dart' as google_web_button;
import '../widgets/aura_widgets.dart';

class AuthScreen extends StatefulWidget {
  const AuthScreen({super.key});

  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _displayNameController = TextEditingController(text: 'Learner');
  bool _registerMode = false;
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    _displayNameController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    FocusScope.of(context).unfocus();
    final form = _formKey.currentState;
    if (form == null || !form.validate()) {
      return;
    }
    context.read<AppState>().clearGoogleSignInError(notify: false);
    setState(() {
      _submitting = true;
      _error = null;
    });
    final state = context.read<AppState>();
    try {
      if (_registerMode) {
        await state.register(
          email: _emailController.text.trim(),
          password: _passwordController.text,
          displayName: _displayNameController.text.trim().isEmpty
              ? 'Learner'
              : _displayNameController.text.trim(),
        );
      } else {
        await state.login(
          email: _emailController.text.trim(),
          password: _passwordController.text,
        );
      }
    } catch (e) {
      setState(() {
        _error = _messageForError(e);
      });
    } finally {
      if (mounted) {
        setState(() {
          _submitting = false;
        });
      }
    }
  }

  String? _validateDisplayName(String? value) {
    if (!_registerMode) {
      return null;
    }
    final trimmed = value?.trim() ?? '';
    if (trimmed.isEmpty) {
      return 'Enter the display name shown in your coach profile.';
    }
    return null;
  }

  String? _validateEmail(String? value) {
    final trimmed = value?.trim() ?? '';
    if (trimmed.isEmpty) {
      return 'Enter your email address.';
    }
    final emailPattern = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');
    if (!emailPattern.hasMatch(trimmed)) {
      return 'Enter a valid email address.';
    }
    return null;
  }

  String? _validatePassword(String? value) {
    final password = value ?? '';
    if (password.isEmpty) {
      return 'Enter your password.';
    }
    if (password.length < 8) {
      return 'Use at least 8 characters.';
    }
    return null;
  }

  String _messageForError(Object error) {
    if (error is ApiException) {
      return error.message;
    }
    return 'Unable to complete authentication right now. Try again in a moment.';
  }

  Future<void> _startGoogleSignIn(AppState state) async {
    FocusScope.of(context).unfocus();
    setState(() {
      _error = null;
    });
    state.clearGoogleSignInError(notify: false);
    try {
      await state.signInWithGoogle();
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = _messageForError(error);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final authError = _error ?? state.googleSignInError;
    final showGoogleSignIn = state.canUseGoogleSignIn;

    return Scaffold(
      body: Container(
        decoration:
            const BoxDecoration(gradient: AuraColors.backgroundGradient),
        child: SafeArea(
          child: LayoutBuilder(
            builder: (context, constraints) {
              final horizontalPadding =
                  constraints.maxWidth >= 900 ? 32.0 : 20.0;

              return SingleChildScrollView(
                padding: EdgeInsets.symmetric(
                    horizontal: horizontalPadding, vertical: 20),
                child: Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 720),
                    child: Form(
                      key: _formKey,
                      child: Column(
                        children: [
                          const SizedBox(height: 24),
                          AuraAvatar(state: 'idle', size: 110),
                          const SizedBox(height: 20),
                          Text(
                            _registerMode
                                ? 'Create your coach account'
                                : 'Sign in to Aura',
                            style: GoogleFonts.spaceGrotesk(
                              fontSize: 28,
                              fontWeight: FontWeight.w800,
                              color: AuraColors.textPrimary,
                            ),
                            textAlign: TextAlign.center,
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Your progress and lesson continuity now belong to your own account.',
                            style: GoogleFonts.spaceGrotesk(
                              fontSize: 14,
                              color: AuraColors.textSecondary,
                              height: 1.45,
                            ),
                            textAlign: TextAlign.center,
                          ),
                          if (!state.backendOnline) ...[
                            const SizedBox(height: 16),
                            Container(
                              width: double.infinity,
                              padding: const EdgeInsets.all(14),
                              decoration: BoxDecoration(
                                color:
                                    AuraColors.warning.withValues(alpha: 0.12),
                                borderRadius: BorderRadius.circular(14),
                                border: Border.all(
                                    color: AuraColors.warning
                                        .withValues(alpha: 0.35)),
                              ),
                              child: Text(
                                'Backend unavailable at ${AppConfig.apiBaseUrl}. Start the API server, then refresh this page before signing in.',
                                style: const TextStyle(
                                  color: AuraColors.textPrimary,
                                  fontSize: 13,
                                  height: 1.4,
                                ),
                              ),
                            ),
                          ],
                          const SizedBox(height: 28),
                          GlassCard(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                if (_registerMode) ...[
                                  TextFormField(
                                    controller: _displayNameController,
                                    validator: _validateDisplayName,
                                    textInputAction: TextInputAction.next,
                                    autofillHints: const [AutofillHints.name],
                                    decoration: const InputDecoration(
                                        labelText: 'Display name'),
                                  ),
                                  const SizedBox(height: 12),
                                ],
                                TextFormField(
                                  controller: _emailController,
                                  validator: _validateEmail,
                                  keyboardType: TextInputType.emailAddress,
                                  textInputAction: TextInputAction.next,
                                  autofillHints: const [AutofillHints.email],
                                  decoration:
                                      const InputDecoration(labelText: 'Email'),
                                ),
                                const SizedBox(height: 12),
                                TextFormField(
                                  controller: _passwordController,
                                  validator: _validatePassword,
                                  obscureText: true,
                                  textInputAction: TextInputAction.done,
                                  autofillHints: _registerMode
                                      ? const [AutofillHints.newPassword]
                                      : const [AutofillHints.password],
                                  onFieldSubmitted: (_) {
                                    if (!_submitting) {
                                      _submit();
                                    }
                                  },
                                  decoration: const InputDecoration(
                                      labelText: 'Password'),
                                ),
                                if (authError != null) ...[
                                  const SizedBox(height: 12),
                                  Text(
                                    authError,
                                    style: const TextStyle(
                                      color: AuraColors.error,
                                      fontSize: 12,
                                      height: 1.35,
                                    ),
                                  ),
                                ],
                                const SizedBox(height: 18),
                                SizedBox(
                                  width: double.infinity,
                                  child: ElevatedButton(
                                    onPressed: _submitting ? null : _submit,
                                    child: Text(_registerMode
                                        ? 'Create account'
                                        : 'Sign in'),
                                  ),
                                ),
                                if (showGoogleSignIn) ...[
                                  const SizedBox(height: 16),
                                  Row(
                                    children: [
                                      const Expanded(
                                        child: Divider(
                                          color: AuraColors.borderDark,
                                        ),
                                      ),
                                      Padding(
                                        padding: const EdgeInsets.symmetric(
                                            horizontal: 12),
                                        child: Text(
                                          'or',
                                          style: GoogleFonts.spaceGrotesk(
                                            color: AuraColors.textSecondary,
                                            fontSize: 12,
                                            fontWeight: FontWeight.w600,
                                          ),
                                        ),
                                      ),
                                      const Expanded(
                                        child: Divider(
                                          color: AuraColors.borderDark,
                                        ),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 16),
                                  if (kIsWeb)
                                    Center(
                                      child: google_web_button
                                          .buildGoogleSignInWebButton(
                                        minimumWidth: 320,
                                      ),
                                    )
                                  else
                                    SizedBox(
                                      width: double.infinity,
                                      child: OutlinedButton.icon(
                                        onPressed: state.googleSignInInProgress
                                            ? null
                                            : () => _startGoogleSignIn(state),
                                        icon: const Icon(
                                          Icons.g_mobiledata,
                                          size: 28,
                                        ),
                                        label: Text(
                                          state.googleSignInInProgress
                                              ? 'Connecting to Google...'
                                              : 'Continue with Google',
                                        ),
                                      ),
                                    ),
                                  if (state.googleSignInInProgress) ...[
                                    const SizedBox(height: 12),
                                    const Center(
                                      child: SizedBox(
                                        width: 18,
                                        height: 18,
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2,
                                          color: AuraColors.primary,
                                        ),
                                      ),
                                    ),
                                  ],
                                ] else ...[
                                  const SizedBox(height: 12),
                                  const Text(
                                    'Continue with email below.',
                                    textAlign: TextAlign.center,
                                    style: TextStyle(
                                      color: AuraColors.textSecondary,
                                      fontSize: 12,
                                      height: 1.4,
                                    ),
                                  ),
                                ],
                              ],
                            ),
                          ),
                          const SizedBox(height: 16),
                          TextButton(
                            onPressed: _submitting
                                ? null
                                : () {
                                    setState(() {
                                      _registerMode = !_registerMode;
                                      _error = null;
                                    });
                                    state.clearGoogleSignInError(notify: false);
                                  },
                            style: TextButton.styleFrom(
                              backgroundColor: AuraColors.surfaceDark,
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 24, vertical: 12),
                            ),
                            child: Text(
                              _registerMode
                                  ? 'Already have an account? Sign in'
                                  : 'Need an account? Register',
                              style: const TextStyle(
                                  fontWeight: FontWeight.bold,
                                  color: AuraColors.primary),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}
