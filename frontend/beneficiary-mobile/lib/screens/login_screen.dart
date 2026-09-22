import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../core/api_client.dart';
import '../core/labels.dart';
import '../core/session.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import '../l10n/generated/app_localizations.dart';

/// Ration card + registered mobile, then a one-time code. The backend verifies both against the beneficiary
/// records; the app never decides who someone is.
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _card = TextEditingController();
  final _mobile = TextEditingController();
  final _otp = TextEditingController();
  bool _otpStep = false, _busy = false;
  String? _error, _devOtp;
  int _cooldown = 0;
  Timer? _timer;

  @override
  void dispose() {
    _timer?.cancel();
    _card.dispose();
    _mobile.dispose();
    _otp.dispose();
    super.dispose();
  }

  void _startCooldown([int seconds = 60]) {
    _timer?.cancel();
    setState(() => _cooldown = seconds);
    _timer = Timer.periodic(const Duration(seconds: 1), (t) {
      if (!mounted) return t.cancel();
      setState(() => _cooldown = _cooldown - 1);
      if (_cooldown <= 0) t.cancel();
    });
  }

  Future<void> _requestOtp() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    final api = context.read<ApiClient>(), l = tr(context);
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final r = await api.requestOtp(_card.text.trim(), _mobile.text.trim());
      if (!mounted) return;
      setState(() {
        _otpStep = true;
        _devOtp = r.devOtp;
        _otp.clear();
      });
      _startCooldown();
    } catch (e) {
      if (mounted) setState(() => _error = errorText(l, e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _verify() async {
    final l = tr(context);
    if (_otp.text.trim().length != 6) {
      setState(() => _error = l.otpInvalidLength);
      return;
    }
    final api = context.read<ApiClient>(), session = context.read<SessionController>();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final token = await api.verifyOtp(_card.text.trim(), _otp.text.trim());
      await session.signIn(token); // the root switches to the signed-in app; this screen is discarded
    } catch (e) {
      if (mounted) setState(() => _error = errorText(l, e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    final expired = context.select<SessionController, bool>((s) => s.expired);
    return Scaffold(
      appBar: AppBar(
        leading: Navigator.of(context).canPop() ? const BackButton() : null,
        title: Text(l.appName),
        actions: const [LanguageButton()],
      ),
      body: SafeArea(
        child: ListView(padding: const EdgeInsets.all(20), children: [
          const SizedBox(height: 8),
          Center(child: BrandMark(size: 64, onDark: false)),
          const SizedBox(height: 18),
          Text(_otpStep ? l.otpTitle : l.loginTitle, textAlign: TextAlign.center, style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 6),
          Text(_otpStep ? l.otpSentTo(_mobile.text.trim()) : l.loginSubtitle, textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppColors.textMuted)),
          const SizedBox(height: 22),
          if (expired && !_otpStep) ...[
            SectionCard(tone: Tone.warn, child: Row(children: [const Icon(Icons.timer_off_outlined, color: AppColors.warn), const SizedBox(width: 12), Expanded(child: Text(l.sessionExpiredBanner))])),
          ],
          if (!_otpStep) _detailsForm(l) else _otpForm(l),
          if (_error != null) ...[
            const SizedBox(height: 14),
            Semantics(
              liveRegion: true,
              child: SectionCard(tone: Tone.bad, child: Row(children: [const Icon(Icons.error_outline, color: AppColors.bad), const SizedBox(width: 12), Expanded(child: Text(_error!, style: const TextStyle(color: AppColors.bad, fontWeight: FontWeight.w600)))])),
            ),
          ],
        ]),
      ),
    );
  }

  Widget _detailsForm(AppLocalizations l) {
    return Form(
      key: _formKey,
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        TextFormField(
          controller: _card,
          textInputAction: TextInputAction.next,
          autofillHints: const [AutofillHints.username],
          decoration: InputDecoration(labelText: l.rationCardLabel, prefixIcon: const Icon(Icons.badge_outlined)),
          validator: (v) => (v == null || v.trim().isEmpty) ? l.fieldRequired : null,
        ),
        const SizedBox(height: 14),
        TextFormField(
          controller: _mobile,
          keyboardType: TextInputType.phone,
          textInputAction: TextInputAction.done,
          inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9+ ]'))],
          decoration: InputDecoration(labelText: l.mobileLabel, prefixIcon: const Icon(Icons.phone_iphone_rounded)),
          validator: (v) => (v == null || v.trim().isEmpty) ? l.fieldRequired : null,
          onFieldSubmitted: (_) => _requestOtp(),
        ),
        const SizedBox(height: 10),
        Text(l.loginHelp, style: const TextStyle(color: AppColors.textMuted, fontSize: 14)),
        const SizedBox(height: 20),
        BigButton(label: l.sendOtp, icon: Icons.sms_outlined, onPressed: _requestOtp, loading: _busy),
      ]),
    );
  }

  Widget _otpForm(AppLocalizations l) {
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      if (_devOtp != null) ...[
        // Shown only when the server runs its development OTP provider (no SMS gateway). Never in production.
        SectionCard(
          tone: Tone.warn,
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [const Icon(Icons.developer_mode_rounded, color: AppColors.warn), const SizedBox(width: 10), Expanded(child: Text(l.devModeBanner(_devOtp!), style: const TextStyle(fontWeight: FontWeight.w700)))]),
            const SizedBox(height: 10),
            BigButton(label: l.useThisCode, style: BigButtonStyle.secondary, onPressed: () => setState(() => _otp.text = _devOtp!)),
          ]),
        ),
      ],
      TextField(
        controller: _otp,
        keyboardType: TextInputType.number,
        maxLength: 6,
        textAlign: TextAlign.center,
        autofillHints: const [AutofillHints.oneTimeCode],
        inputFormatters: [FilteringTextInputFormatter.digitsOnly],
        style: const TextStyle(fontSize: 28, letterSpacing: 10, fontWeight: FontWeight.w800),
        decoration: InputDecoration(labelText: l.otpLabel, counterText: ''),
        onSubmitted: (_) => _verify(),
      ),
      const SizedBox(height: 16),
      BigButton(label: l.verifyContinue, icon: Icons.verified_user_outlined, onPressed: _verify, loading: _busy),
      const SizedBox(height: 10),
      TextButton(
        onPressed: (_cooldown > 0 || _busy) ? null : _requestOtp,
        style: TextButton.styleFrom(minimumSize: const Size.fromHeight(52)),
        child: Text(_cooldown > 0 ? l.resendIn('$_cooldown') : l.resendOtp),
      ),
      TextButton(
        onPressed: _busy ? null : () => setState(() {
          _otpStep = false;
          _error = null;
          _devOtp = null;
        }),
        style: TextButton.styleFrom(minimumSize: const Size.fromHeight(52)),
        child: Text(l.changeNumber),
      ),
    ]);
  }
}
