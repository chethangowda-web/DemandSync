import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_client.dart';
import '../core/format.dart';
import '../core/labels.dart';
import '../core/models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';

/// "Where is my ration?" An eight-stage journey read from real records. A stage that has no record yet is shown
/// as pending; nothing is estimated, and the vehicle position appears only if the vehicle actually reported one.
class TrackScreen extends StatefulWidget {
  const TrackScreen({super.key});

  @override
  State<TrackScreen> createState() => _TrackScreenState();
}

class _TrackScreenState extends State<TrackScreen> {
  String? _cycle; // null = the current cycle

  Future<({Journey journey, List<String> cycles})> _load(ApiClient api) async {
    final journey = await api.tracking(cycle: _cycle);
    final intents = await api.intents();
    final cycles = {journey.cycle, for (final i in intents) i.cycle}.toList()..sort((a, b) => b.compareTo(a));
    return (journey: journey, cycles: cycles);
  }

  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    final api = context.read<ApiClient>();
    final loc = Localizations.localeOf(context).languageCode;
    return Scaffold(
      appBar: AppBar(title: Text(l.trackTitle), actions: const [LanguageButton()]),
      body: AsyncBody<({Journey journey, List<String> cycles})>(
        key: ValueKey(_cycle),
        load: () => _load(api),
        builder: (context, data, reload) {
          final j = data.journey;
          final t = Theme.of(context).textTheme;
          return RefreshIndicator(
            onRefresh: reload,
            child: ListView(padding: const EdgeInsets.all(16), children: [
              if (data.cycles.length > 1)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Wrap(spacing: 8, runSpacing: 8, children: [
                    for (final c in data.cycles)
                      ChoiceChip(
                        label: Text(cycleLabel(c, loc)),
                        selected: c == j.cycle,
                        onSelected: (_) => setState(() => _cycle = c),
                        materialTapTargetSize: MaterialTapTargetSize.padded,
                      ),
                  ]),
                ),
              Semantics(header: true, child: Text(l.journeyOf(cycleLabel(j.cycle, loc)), style: t.titleLarge)),
              const SizedBox(height: 12),
              SectionCard(
                padding: const EdgeInsets.fromLTRB(16, 18, 16, 6),
                child: Column(children: [for (var i = 0; i < j.steps.length; i++) _StepTile(step: j.steps[i], last: i == j.steps.length - 1)]),
              ),
              if (j.telemetry != null) _VehicleCard(j: j) else if (j.telemetryNote == 'LIVE_LOCATION_UNAVAILABLE') _NoLocationCard(),
            ]),
          );
        },
      ),
    );
  }
}

class _StepTile extends StatelessWidget {
  const _StepTile({required this.step, required this.last});
  final JourneyStep step;
  final bool last;

  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    final loc = Localizations.localeOf(context).languageCode;
    final t = Theme.of(context).textTheme;
    final (icon, color, tone) = switch (step.status) {
      'DONE' => (Icons.check_circle_rounded, AppColors.good, Tone.good),
      'ACTIVE' => (Icons.radio_button_checked_rounded, AppColors.blue, Tone.info),
      'DELAYED' => (Icons.pause_circle_rounded, AppColors.warn, Tone.warn),
      'UNAVAILABLE' => (Icons.remove_circle_outline_rounded, AppColors.textMuted, Tone.neutral),
      _ => (Icons.radio_button_unchecked_rounded, AppColors.border, Tone.neutral),
    };
    final detail = stepDetailText(l, step);
    final pending = step.status == 'PENDING';
    return Semantics(
      container: true,
      label: '${stageLabel(l, step.key)}. ${stepStateLabel(l, step.status)}.${step.at != null ? ' ${dateTimeText(step.at!, loc)}.' : ''} $detail',
      excludeSemantics: true,
      child: IntrinsicHeight(
        child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          SizedBox(
            width: 34,
            child: Column(children: [
              Icon(icon, color: color, size: 30),
              if (!last) Expanded(child: Container(width: 3, margin: const EdgeInsets.symmetric(vertical: 2), color: step.status == 'DONE' ? AppColors.good.withValues(alpha: 0.5) : AppColors.border)),
            ]),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(bottom: 18),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(stageLabel(l, step.key), style: t.titleMedium?.copyWith(color: pending ? AppColors.textMuted : AppColors.text)),
                const SizedBox(height: 4),
                Wrap(spacing: 8, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: [
                  StatusChip(label: pending ? l.notYetAvailable : stepStateLabel(l, step.status), tone: tone),
                  if (step.at != null) Text(dateTimeText(step.at!, loc), style: t.bodyMedium?.copyWith(color: AppColors.textMuted)),
                ]),
                if (detail.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 6), child: Text(detail, style: t.bodyMedium?.copyWith(color: AppColors.textMuted))),
              ]),
            ),
          ),
        ]),
      ),
    );
  }
}

class _VehicleCard extends StatelessWidget {
  const _VehicleCard({required this.j});
  final Journey j;

  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    final loc = Localizations.localeOf(context).languageCode;
    final v = j.telemetry!;
    return SectionCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [const Icon(Icons.local_shipping_rounded, color: AppColors.blue), const SizedBox(width: 10), Text(l.liveTracking, style: Theme.of(context).textTheme.titleMedium)]),
        const SizedBox(height: 8),
        KeyValueRow(label: l.vehicleLabel, value: v.vehicleNumber),
        KeyValueRow(label: l.lastUpdate, value: dateTimeText(v.lastUpdate, loc)),
        KeyValueRow(label: l.locationLabel, value: '${v.latitude.toStringAsFixed(5)}, ${v.longitude.toStringAsFixed(5)}'),
        if (j.route != null) ...[
          KeyValueRow(label: l.trackTitle, value: l.routeStop('${j.route!.yourStop}', '${j.route!.stopsTotal}')),
          if (j.route!.plannedEtaMinutes != null) Padding(padding: const EdgeInsets.only(top: 4), child: Text(l.plannedEta(kgText(j.route!.plannedEtaMinutes!)), style: const TextStyle(color: AppColors.textMuted))),
        ],
      ]),
    );
  }
}

class _NoLocationCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    return SectionCard(
      tone: Tone.neutral,
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Icon(Icons.location_off_rounded, color: AppColors.textMuted),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(l.liveLocationUnavailable, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 4),
            Text(l.liveLocationUnavailableBody),
          ]),
        ),
      ]),
    );
  }
}
