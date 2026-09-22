import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_client.dart';
import '../core/format.dart';
import '../core/models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'review_screen.dart';

/// What the beneficiary wants to collect this cycle. The limits shown here come from the backend
/// (statutory entitlement minus recorded collections); the backend validates again on submit.
class PlanScreen extends StatefulWidget {
  const PlanScreen({super.key, required this.home});
  final HomeData home;

  @override
  State<PlanScreen> createState() => _PlanScreenState();
}

class _PlanScreenState extends State<PlanScreen> {
  late Future<List<Fps>> _fps;
  String? _fpsId;
  int _rice = 0, _wheat = 0;
  String _mode = 'SELF';

  Entitlement get _e => widget.home.entitlement!;

  @override
  void initState() {
    super.initState();
    _fps = context.read<ApiClient>().eligibleFps();
    if (widget.home.fps.isActive) _fpsId = widget.home.fps.id;
  }

  void _retry() => setState(() => _fps = context.read<ApiClient>().eligibleFps());

  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    final t = Theme.of(context).textTheme;
    final e = _e;
    final total = _rice + _wheat;
    final valid = _fpsId != null && total > 0 && _rice <= e.remainingRiceKg && _wheat <= e.remainingWheatKg;

    return Scaffold(
      appBar: AppBar(title: Text(l.planTitle)),
      body: SafeArea(
        child: Column(children: [
          _Steps(current: 0, labels: [l.stepSelect, l.stepReview, l.stepSubmit]),
          Expanded(
            child: ListView(padding: const EdgeInsets.fromLTRB(16, 4, 16, 16), children: [
              Semantics(header: true, child: Text(l.chooseFps, style: t.titleLarge)),
              Text(l.nearestFirst, style: t.bodyMedium?.copyWith(color: AppColors.textMuted)),
              const SizedBox(height: 10),
              FutureBuilder<List<Fps>>(
                future: _fps,
                builder: (context, snap) {
                  if (snap.connectionState != ConnectionState.done) return const Padding(padding: EdgeInsets.all(24), child: Center(child: CircularProgressIndicator()));
                  if (snap.hasError) return SizedBox(height: 200, child: ErrorView(error: snap.error!, onRetry: _retry));
                  return Column(children: [for (final f in snap.data!) _FpsTile(fps: f, selected: f.id == _fpsId, onTap: f.isActive ? () => setState(() => _fpsId = f.id) : null)]);
                },
              ),
              const SizedBox(height: 14),
              Semantics(header: true, child: Text(l.chooseQuantity, style: t.titleLarge)),
              const SizedBox(height: 10),
              _QuantityCard(label: l.riceKg, icon: Icons.rice_bowl_outlined, value: _rice, max: e.remainingRiceKg.toInt(), onChanged: (v) => setState(() => _rice = v)),
              _QuantityCard(label: l.wheatKg, icon: Icons.grain_rounded, value: _wheat, max: e.remainingWheatKg.toInt(), onChanged: (v) => setState(() => _wheat = v)),
              const SizedBox(height: 4),
              Semantics(header: true, child: Text(l.collectionMode, style: t.titleMedium)),
              const SizedBox(height: 8),
              SegmentedButton<String>(
                showSelectedIcon: true,
                style: SegmentedButton.styleFrom(minimumSize: const Size(0, 52)),
                segments: [
                  ButtonSegment(value: 'SELF', label: Text(l.modeSelf), icon: const Icon(Icons.person_rounded)),
                  ButtonSegment(value: 'AUTHORIZED_PERSON', label: Text(l.modeAuthorized), icon: const Icon(Icons.badge_rounded)),
                ],
                selected: {_mode},
                onSelectionChanged: (s) => setState(() => _mode = s.first),
              ),
              const SizedBox(height: 16),
              // live calculation
              SectionCard(
                tone: Tone.info,
                child: Column(children: [
                  KeyValueRow(label: l.calcEntitlement, value: l.kgValue(kgText(e.totalKg))),
                  KeyValueRow(label: l.calcCollected, value: l.kgValue(kgText(e.collectedTotalKg))),
                  KeyValueRow(label: l.calcRemaining, value: l.kgValue(kgText(e.remainingTotalKg))),
                  const Divider(),
                  KeyValueRow(label: l.calcRequested, value: l.kgValue('$total'), strong: true),
                ]),
              ),
            ]),
          ),
          Container(
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 12),
            decoration: const BoxDecoration(color: Colors.white, border: Border(top: BorderSide(color: AppColors.border))),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              if (total == 0) Padding(padding: const EdgeInsets.only(bottom: 8), child: Text(l.enterQuantity, style: const TextStyle(color: AppColors.textMuted))),
              BigButton(
                label: l.reviewPlan,
                icon: Icons.arrow_forward_rounded,
                onPressed: valid
                    ? () async {
                        final fps = (await _fps).firstWhere((f) => f.id == _fpsId);
                        if (!context.mounted) return;
                        Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => ReviewScreen(home: widget.home, fps: fps, riceKg: _rice, wheatKg: _wheat, mode: _mode)));
                      }
                    : null,
              ),
            ]),
          ),
        ]),
      ),
    );
  }
}

class _Steps extends StatelessWidget {
  const _Steps({required this.current, required this.labels});
  final int current;
  final List<String> labels;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
      child: Row(children: [
        for (var i = 0; i < labels.length; i++) ...[
          Expanded(
            child: Semantics(
              label: '${i + 1}. ${labels[i]}${i == current ? ' (current)' : ''}',
              excludeSemantics: true,
              child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                CircleAvatar(radius: 14, backgroundColor: i <= current ? AppColors.blue : AppColors.border, child: Text('${i + 1}', style: TextStyle(color: i <= current ? Colors.white : AppColors.textMuted, fontWeight: FontWeight.w800, fontSize: 13))),
                const SizedBox(width: 6),
                Flexible(child: Text(labels[i], overflow: TextOverflow.ellipsis, style: TextStyle(fontWeight: i == current ? FontWeight.w800 : FontWeight.w500, fontSize: 13))),
              ]),
            ),
          ),
        ],
      ]),
    );
  }
}

class _FpsTile extends StatelessWidget {
  const _FpsTile({required this.fps, required this.selected, required this.onTap});
  final Fps fps;
  final bool selected;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    final t = Theme.of(context).textTheme;
    return Semantics(
      selected: selected,
      button: true,
      enabled: onTap != null,
      label: '${fps.name}. ${fps.distanceKm != null ? l.distanceKm(kgText(fps.distanceKm!)) : ''}. ${fps.isActive ? '' : l.shopNotActive}',
      excludeSemantics: true,
      child: Card(
        elevation: 0,
        margin: const EdgeInsets.only(bottom: 10),
        color: selected ? AppColors.blueSoft : (fps.isActive ? Colors.white : const Color(0xFFF1F3F7)),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: BorderSide(color: selected ? AppColors.blue : AppColors.border, width: selected ? 2 : 1)),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Row(children: [
              Icon(selected ? Icons.radio_button_checked : Icons.radio_button_off, color: onTap == null ? AppColors.border : AppColors.blue, size: 28),
              const SizedBox(width: 12),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(fps.name, style: t.titleMedium),
                  const SizedBox(height: 2),
                  Text('${fps.taluk}${fps.openingHours != null ? ' · ${fps.openingHours}' : ''}', style: t.bodyMedium?.copyWith(color: AppColors.textMuted)),
                  const SizedBox(height: 6),
                  Wrap(spacing: 8, runSpacing: 6, children: [
                    if (fps.isCurrent) StatusChip(label: l.yourCurrentShop, tone: Tone.info, icon: Icons.home_work_outlined),
                    if (!fps.isActive) StatusChip(label: l.shopNotActive, tone: Tone.warn, icon: Icons.block_rounded),
                    if (fps.distanceKm != null) StatusChip(label: l.distanceKm(kgText(fps.distanceKm!)), tone: Tone.neutral, icon: Icons.near_me_outlined),
                  ]),
                ]),
              ),
            ]),
          ),
        ),
      ),
    );
  }
}

class _QuantityCard extends StatelessWidget {
  const _QuantityCard({required this.label, required this.icon, required this.value, required this.max, required this.onChanged});
  final String label;
  final IconData icon;
  final int value, max;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    final t = Theme.of(context).textTheme;
    return SectionCard(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(children: [
        Icon(icon, color: AppColors.blue, size: 28),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(label, style: t.titleMedium),
            Text(l.upTo('$max'), style: t.bodyMedium?.copyWith(color: AppColors.textMuted)),
          ]),
        ),
        IconButton.filledTonal(
          onPressed: value > 0 ? () => onChanged(value - 1) : null,
          icon: const Icon(Icons.remove_rounded),
          tooltip: l.decrease(label),
          style: IconButton.styleFrom(minimumSize: const Size(52, 52)),
        ),
        SizedBox(width: 56, child: Semantics(liveRegion: true, label: '$label $value', excludeSemantics: true, child: Text('$value', textAlign: TextAlign.center, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w800)))),
        IconButton.filled(
          onPressed: value < max ? () => onChanged(value + 1) : null,
          icon: const Icon(Icons.add_rounded),
          tooltip: l.increase(label),
          style: IconButton.styleFrom(minimumSize: const Size(52, 52), backgroundColor: AppColors.blue),
        ),
      ]),
    );
  }
}
