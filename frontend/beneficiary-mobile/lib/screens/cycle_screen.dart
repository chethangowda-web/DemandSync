import 'package:flutter/material.dart';

import '../core/format.dart';
import '../core/labels.dart';
import '../core/models.dart';
import '../core/theme.dart';
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
    return Scaffold(
      appBar: AppBar(title: Text(l.cycleTitle)),
      body: c == null
          ? Center(child: Text(l.noticeNoCycle))
          : ListView(padding: const EdgeInsets.all(16), children: [
              SectionCard(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Semantics(
                    header: true,
                    excludeSemantics: true,
                    child: SectionHeader(
                      icon: Icons.calendar_month_rounded,
                      title: cycleLabel(c.cycle, loc),
                      subtitle: l.cycleSubtitle,
                      badgeColor: AppColors.blue,
                      trailing: home.statusKey != null
                          ? StatusChip(label: stageLabel(l, home.statusKey!), tone: toneForStatusKey(home.statusKey), icon: c.windowOpen ? Icons.lock_open_rounded : Icons.lock_clock_outlined)
                          : null,
                    ),
                  ),
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
                  SectionHeader(icon: Icons.info_outline_rounded, title: l.whatThisMeans, badgeColor: AppColors.blue),
                  const SizedBox(height: 8),
                  Text(cycleExplanation(l, home)),
                ]),
              ),
            ]),
    );
  }
}
