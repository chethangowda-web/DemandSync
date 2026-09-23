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
          final used = e.totalKg == 0 ? 0.0 : (e.collectedTotalKg / e.totalKg).clamp(0.0, 1.0).toDouble();
          return RefreshIndicator(
            onRefresh: reload,
            child: ListView(padding: const EdgeInsets.all(16), children: [
              SectionCard(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  SectionHeader(icon: Icons.verified_user_rounded, title: l.monthlyEntitlement, subtitle: cycleLabel(e.cycle, loc), badgeColor: AppColors.blue),
                  const SizedBox(height: 14),
                  Container(
                    decoration: BoxDecoration(color: AppColors.goodSoft, borderRadius: BorderRadius.circular(12), border: Border.all(color: AppColors.good.withValues(alpha: 0.25))),
                    padding: const EdgeInsets.all(14),
                    child: Row(children: [
                      const IconBadge(icon: Icons.donut_large_rounded, color: AppColors.good, size: 44),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text(l.kgValue(kgText(e.totalKg)), style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w800, color: AppColors.good, height: 1)),
                          const SizedBox(height: 2),
                          Text(l.total, style: const TextStyle(color: AppColors.textMuted, fontSize: 13, fontWeight: FontWeight.w600)),
                        ]),
                      ),
                    ]),
                  ),
                  const SizedBox(height: 12),
                  KeyValueRow(label: l.rice, value: l.kgValue(kgText(e.riceKg))),
                  KeyValueRow(label: l.wheat, value: l.kgValue(kgText(e.wheatKg))),
                ]),
              ),
              SectionCard(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  SectionHeader(icon: Icons.pie_chart_rounded, title: l.remainingThisCycle, badgeColor: AppColors.blue),
                  const SizedBox(height: 14),
                  KeyValueRow(label: l.alreadyCollected, value: l.kgValue(kgText(e.collectedTotalKg))),
                  const SizedBox(height: 4),
                  Semantics(
                    label: '${l.alreadyCollected} ${l.kgValue(kgText(e.collectedTotalKg))} / ${l.kgValue(kgText(e.totalKg))}',
                    child: ClipRRect(borderRadius: BorderRadius.circular(8), child: LinearProgressIndicator(value: used, minHeight: 12, backgroundColor: AppColors.blueSoft, color: AppColors.blue)),
                  ),
                  const SizedBox(height: 14),
                  Container(
                    decoration: BoxDecoration(color: AppColors.blueSoft, borderRadius: BorderRadius.circular(12)),
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                    child: Column(children: [
                      KeyValueRow(label: l.remainingThisCycle, value: l.kgValue(kgText(e.remainingTotalKg)), strong: true),
                      KeyValueRow(label: '  ${l.rice}', value: l.kgValue(kgText(e.remainingRiceKg))),
                      KeyValueRow(label: '  ${l.wheat}', value: l.kgValue(kgText(e.remainingWheatKg))),
                    ]),
                  ),
                ]),
              ),
              SectionCard(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  SectionHeader(icon: Icons.groups_rounded, title: l.householdDetails, badgeColor: AppColors.navy),
                  const SizedBox(height: 10),
                  KeyValueRow(label: l.schemeLabel, value: schemeLabel(l, e.scheme)),
                  KeyValueRow(label: l.householdLabel, value: l.householdMembers('${e.householdSize}')),
                  KeyValueRow(label: l.cycleData, value: cycleLabel(e.cycle, loc)),
                ]),
              ),
              SectionCard(
                tone: Tone.info,
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const IconBadge(icon: Icons.info_outline_rounded, color: AppColors.blue, size: 34),
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
