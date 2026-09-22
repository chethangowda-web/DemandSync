import 'package:flutter/material.dart';

import '../core/format.dart';
import '../core/labels.dart';
import '../core/models.dart';
import '../widgets/common.dart';

/// The current cycle in plain words: its period, the choice window, and what its status means for me.
class CycleScreen extends StatelessWidget {
  const CycleScreen({super.key, required this.home});
  final HomeData home;

  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    final loc = Localizations.localeOf(context).languageCode;
    final c = home.cycle;
    final t = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: Text(l.cycleTitle)),
      body: c == null
          ? Center(child: Text(l.noticeNoCycle))
          : ListView(padding: const EdgeInsets.all(16), children: [
              SectionCard(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Semantics(header: true, child: Text(cycleLabel(c.cycle, loc), style: t.headlineSmall)),
                  const SizedBox(height: 12),
                  if (home.statusKey != null) StatusChip(label: stageLabel(l, home.statusKey!), tone: toneForStatusKey(home.statusKey), icon: c.windowOpen ? Icons.lock_open_rounded : Icons.lock_clock_outlined),
                  const SizedBox(height: 14),
                  KeyValueRow(label: l.periodLabel, value: '${dateText(c.periodStart, loc)} – ${dateText(c.periodEnd, loc)}'),
                  KeyValueRow(
                    label: l.windowLabel,
                    value: (c.windowStart != null && c.windowEnd != null) ? '${dateText(c.windowStart!, loc)} – ${dateText(c.windowEnd!, loc)}' : l.dataUnavailable,
                  ),
                  KeyValueRow(label: l.statusLabel, value: home.statusKey == null ? l.dataUnavailable : stageLabel(l, home.statusKey!)),
                ]),
              ),
              SectionCard(
                tone: Tone.info,
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(l.whatThisMeans, style: t.titleMedium),
                  const SizedBox(height: 6),
                  Text(cycleExplanation(l, home)),
                ]),
              ),
            ]),
    );
  }
}
