import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_client.dart';
import '../core/api_exception.dart';
import '../core/format.dart';
import '../core/labels.dart';
import '../core/models.dart';
import '../core/session.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'receipt_screen.dart';

/// The last look before the plan is recorded. Submitting posts to the backend, which validates everything again.
class ReviewScreen extends StatefulWidget {
  const ReviewScreen({super.key, required this.home, required this.fps, required this.riceKg, required this.wheatKg, required this.mode});
  final HomeData home;
  final Fps fps;
  final int riceKg, wheatKg;
  final String mode;

  @override
  State<ReviewScreen> createState() => _ReviewScreenState();
}

class _ReviewScreenState extends State<ReviewScreen> {
  bool _busy = false;
  String? _error;

  Future<void> _submit() async {
    final l = tr(context);
    final api = context.read<ApiClient>(), session = context.read<SessionController>();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final receipt = await api.submitIntent(fpsId: widget.fps.id, riceKg: widget.riceKg, wheatKg: widget.wheatKg, mode: widget.mode);
      session.bump(); // home, tracking and history now reload from the server
      if (!mounted) return;
      Navigator.of(context).pushAndRemoveUntil(MaterialPageRoute<void>(builder: (_) => ReceiptScreen(receipt: receipt, justSubmitted: true)), (r) => r.isFirst);
    } catch (e) {
      if (!mounted) return;
      if (e is ApiException && e.code == 'INTENT_DUPLICATE') session.bump();
      setState(() => _error = errorText(l, e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    final loc = Localizations.localeOf(context).languageCode;
    final t = Theme.of(context).textTheme;
    final e = widget.home.entitlement!, cycle = widget.home.cycle!;
    final total = widget.riceKg + widget.wheatKg;
    return Scaffold(
      appBar: AppBar(title: Text(l.reviewTitle)),
      body: SafeArea(
        child: Column(children: [
          Expanded(
            child: ListView(padding: const EdgeInsets.all(16), children: [
              SectionCard(
                child: Column(children: [
                  KeyValueRow(label: l.reviewCycle, value: cycleLabel(cycle.cycle, loc)),
                  KeyValueRow(label: l.reviewFps, value: widget.fps.name),
                  KeyValueRow(label: l.reviewMode, value: modeLabel(l, widget.mode)),
                  const Divider(),
                  KeyValueRow(label: l.rice, value: l.kgValue('${widget.riceKg}')),
                  KeyValueRow(label: l.wheat, value: l.kgValue('${widget.wheatKg}')),
                  KeyValueRow(label: l.total, value: l.kgValue('$total'), strong: true),
                  const Divider(),
                  KeyValueRow(label: l.reviewRemainingAfter, value: l.kgValue(kgText(e.remainingTotalKg - total))),
                ]),
              ),
              SectionCard(
                tone: Tone.warn,
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Icon(Icons.warning_amber_rounded, color: AppColors.warn),
                  const SizedBox(width: 12),
                  Expanded(child: Text(l.reviewWarning, style: t.bodyMedium?.copyWith(fontWeight: FontWeight.w600))),
                ]),
              ),
              if (_error != null) Semantics(liveRegion: true, child: SectionCard(tone: Tone.bad, child: Row(children: [const Icon(Icons.error_outline, color: AppColors.bad), const SizedBox(width: 12), Expanded(child: Text(_error!, style: const TextStyle(color: AppColors.bad, fontWeight: FontWeight.w600)))]))),
            ]),
          ),
          Container(
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 12),
            decoration: const BoxDecoration(color: Colors.white, border: Border(top: BorderSide(color: AppColors.border))),
            child: BigButton(label: _busy ? l.submitting : l.submitIntent, icon: Icons.send_rounded, onPressed: _busy ? null : _submit, loading: _busy),
          ),
        ]),
      ),
    );
  }
}
