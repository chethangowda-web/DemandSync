import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_client.dart';
import '../core/format.dart';
import '../core/labels.dart';
import '../core/models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';

/// Statutory entitlement is read-only here: it is set by the government and no plan can change it.
class EntitlementScreen extends StatelessWidget {
  const EntitlementScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    final api = context.read<ApiClient>();
    final loc = Localizations.localeOf(context).languageCode;
    return Scaffold(
      appBar: AppBar(title: Text(l.entitlementTitle)),
      body: AsyncBody<Entitlement>(
        load: api.entitlement,
        builder: (context, e, reload) {
          final t = Theme.of(context).textTheme;
          final used = e.totalKg == 0 ? 0.0 : (e.collectedTotalKg / e.totalKg).clamp(0.0, 1.0).toDouble();
          return RefreshIndicator(
            onRefresh: reload,
            child: ListView(padding: const EdgeInsets.all(16), children: [
              SectionCard(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(l.monthlyEntitlement, style: t.bodyMedium?.copyWith(color: AppColors.textMuted)),
                  Text(cycleLabel(e.cycle, loc), style: t.titleLarge),
                  const SizedBox(height: 10),
                  KeyValueRow(label: l.rice, value: l.kgValue(kgText(e.riceKg))),
                  KeyValueRow(label: l.wheat, value: l.kgValue(kgText(e.wheatKg))),
                  const Divider(),
                  KeyValueRow(label: l.total, value: l.kgValue(kgText(e.totalKg)), strong: true),
                ]),
              ),
              SectionCard(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  KeyValueRow(label: l.alreadyCollected, value: l.kgValue(kgText(e.collectedTotalKg))),
                  const SizedBox(height: 4),
                  Semantics(
                    label: '${l.alreadyCollected} ${l.kgValue(kgText(e.collectedTotalKg))} / ${l.kgValue(kgText(e.totalKg))}',
                    child: ClipRRect(borderRadius: BorderRadius.circular(8), child: LinearProgressIndicator(value: used, minHeight: 12, backgroundColor: AppColors.blueSoft, color: AppColors.blue)),
                  ),
                  const SizedBox(height: 14),
                  KeyValueRow(label: l.remainingThisCycle, value: l.kgValue(kgText(e.remainingTotalKg)), strong: true),
                  KeyValueRow(label: '  ${l.rice}', value: l.kgValue(kgText(e.remainingRiceKg))),
                  KeyValueRow(label: '  ${l.wheat}', value: l.kgValue(kgText(e.remainingWheatKg))),
                ]),
              ),
              SectionCard(
                child: Column(children: [
                  KeyValueRow(label: l.schemeLabel, value: schemeLabel(l, e.scheme)),
                  KeyValueRow(label: l.householdLabel, value: l.householdMembers('${e.householdSize}')),
                  KeyValueRow(label: l.cycleData, value: cycleLabel(e.cycle, loc)),
                ]),
              ),
              SectionCard(
                tone: Tone.info,
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Icon(Icons.info_outline, color: AppColors.blue),
                  const SizedBox(width: 12),
                  Expanded(child: Text('${l.entitlementExplain}\n${l.entitlementReadOnly}')),
                ]),
              ),
            ]),
          );
        },
      ),
    );
  }
}
