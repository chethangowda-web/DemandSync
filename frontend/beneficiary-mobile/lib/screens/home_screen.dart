import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_client.dart';
import '../core/format.dart';
import '../core/labels.dart';
import '../core/models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import '../l10n/generated/app_localizations.dart';
import 'cycle_screen.dart';
import 'entitlement_screen.dart';
import 'plan_screen.dart';
import 'receipt_screen.dart';

/// The service home. It answers one question: what can I do right now?
class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiClient>();
    return AsyncBody<HomeData>(
      load: api.home,
      builder: (context, h, reload) => RefreshIndicator(onRefresh: reload, child: _HomeBody(home: h)),
    );
  }
}

class _HomeBody extends StatelessWidget {
  const _HomeBody({required this.home});
  final HomeData home;

  String _greeting(AppLocalizations l) {
    final hour = DateTime.now().hour;
    return hour < 12 ? l.goodMorning : (hour < 17 ? l.goodAfternoon : l.goodEvening);
  }

  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    final loc = Localizations.localeOf(context).languageCode;
    final h = home, cycle = h.cycle, e = h.entitlement;
    final t = Theme.of(context).textTheme;
    final canPlan = cycle != null && cycle.windowOpen && h.intent == null;

    return ListView(padding: EdgeInsets.zero, children: [
      // header
      Container(
        padding: EdgeInsets.fromLTRB(20, MediaQuery.of(context).padding.top + 8, 12, 26),
        decoration: const BoxDecoration(
          gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [AppColors.navy, AppColors.blue]),
          borderRadius: BorderRadius.vertical(bottom: Radius.circular(28)),
        ),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const SizedBox(height: 10),
              Text(_greeting(l), style: const TextStyle(color: Color(0xFFCFE0FF), fontSize: 15)),
              const SizedBox(height: 2),
              Semantics(header: true, child: Text(h.beneficiary.name, style: t.headlineSmall?.copyWith(color: Colors.white))),
              const SizedBox(height: 4),
              Text(l.rationCardShort(maskedCard(h.beneficiary.rationCardId)), style: const TextStyle(color: Color(0xFFCFE0FF), fontSize: 14)),
            ]),
          ),
          const LanguageButton(),
        ]),
      ),
      Padding(
        padding: const EdgeInsets.fromLTRB(16, 18, 16, 24),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          if (h.notice != null && noticeText(l, h.notice!, loc).isNotEmpty)
            SectionCard(
              tone: switch (h.notice!.code) { 'FPS_NOT_ACTIVE' || 'WINDOW_CLOSED_NO_INTENT' || 'NO_CYCLE' => Tone.warn, 'RATION_AT_FPS' => Tone.good, _ => Tone.info },
              child: Row(children: [
                Icon(switch (h.notice!.code) { 'RATION_AT_FPS' => Icons.check_circle_outline, 'INTENT_RECORDED' => Icons.task_alt, _ => Icons.info_outline }, color: toneColors(switch (h.notice!.code) { 'FPS_NOT_ACTIVE' || 'WINDOW_CLOSED_NO_INTENT' || 'NO_CYCLE' => Tone.warn, 'RATION_AT_FPS' => Tone.good, _ => Tone.info }).fg),
                const SizedBox(width: 12),
                Expanded(child: Text(noticeText(l, h.notice!, loc), style: t.bodyMedium?.copyWith(fontWeight: FontWeight.w600))),
              ]),
            ),
          // primary actions first: what can I do right now?
          if (canPlan)
            BigButton(
              label: l.planMyCollection,
              icon: Icons.edit_calendar_rounded,
              onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => PlanScreen(home: h))),
            ),
          if (h.intent != null)
            BigButton(
              label: l.viewMyPlan,
              icon: Icons.receipt_long_rounded,
              onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => ReceiptScreen(receipt: h.intent!))),
            ),
          const SizedBox(height: 10),
          BigButton(label: l.trackMyRation, icon: Icons.local_shipping_outlined, style: BigButtonStyle.secondary, onPressed: () => context.read<TabIndex>().go(1)),
          const SizedBox(height: 18),
          // current cycle
          SectionCard(
            onTap: cycle == null ? null : () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => CycleScreen(home: h))),
            child: cycle == null
                ? Text(l.noticeNoCycle)
                : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(children: [Expanded(child: Text(l.currentCycle, style: t.bodyMedium?.copyWith(color: AppColors.textMuted)))]),
                    if (h.statusKey != null) ...[
                      const SizedBox(height: 4),
                      Wrap(children: [StatusChip(label: stageLabel(l, h.statusKey!), tone: toneForStatusKey(h.statusKey), icon: h.statusKey == 'CHOICE_WINDOW_CLOSED' ? Icons.lock_clock_outlined : Icons.circle)]),
                    ],
                    const SizedBox(height: 6),
                    Semantics(header: true, child: Text(cycleLabel(cycle.cycle, loc), style: t.titleLarge)),
                    const SizedBox(height: 6),
                    Text(
                      (cycle.windowStart != null && cycle.windowEnd != null) ? l.collectionWindow(shortDate(cycle.windowStart!, loc), shortDate(cycle.windowEnd!, loc)) : l.dataUnavailable,
                      style: t.bodyMedium?.copyWith(color: AppColors.textMuted),
                    ),
                  ]),
          ),
          // entitlement
          SectionCard(
            onTap: cycle == null ? null : () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const EntitlementScreen())),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [Expanded(child: Text(l.myEntitlement, style: t.titleMedium)), const Icon(Icons.chevron_right_rounded, color: AppColors.textMuted)]),
              const SizedBox(height: 12),
              Row(children: [
                _Stat(label: l.rice, value: l.kgValue(kgText(h.statutory.rice)), icon: Icons.rice_bowl_outlined),
                const SizedBox(width: 10),
                _Stat(label: l.wheat, value: l.kgValue(kgText(h.statutory.wheat)), icon: Icons.grain_rounded),
                const SizedBox(width: 10),
                _Stat(label: l.total, value: l.kgValue(kgText(h.statutory.total)), icon: Icons.scale_outlined, strong: true),
              ]),
              if (e != null) ...[
                const Divider(height: 26),
                Row(children: [
                  Expanded(child: Text(l.remaining, style: t.bodyLarge?.copyWith(fontWeight: FontWeight.w600))),
                  Text(l.kgValue(kgText(e.remainingTotalKg)), style: t.titleLarge?.copyWith(color: e.remainingTotalKg > 0 ? AppColors.good : AppColors.textMuted)),
                ]),
                const SizedBox(height: 4),
                Row(children: [
                  Expanded(child: Text(l.collected, style: t.bodyMedium?.copyWith(color: AppColors.textMuted))),
                  Text(l.kgValue(kgText(e.collectedTotalKg)), style: t.bodyMedium?.copyWith(color: AppColors.textMuted)),
                ]),
              ],
            ]),
          ),
          // current shop
          SectionCard(
            tone: h.fps.isActive ? null : Tone.warn,
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                const Icon(Icons.storefront_rounded, color: AppColors.blue),
                const SizedBox(width: 10),
                Expanded(child: Text(l.currentFps, style: t.bodyMedium?.copyWith(color: AppColors.textMuted))),
              ]),
              const SizedBox(height: 6),
              Text(h.fps.name, style: t.titleMedium),
              if (!h.fps.isActive) Padding(padding: const EdgeInsets.only(top: 6), child: StatusChip(label: l.shopNotActive, tone: Tone.warn, icon: Icons.block_rounded)),
              const SizedBox(height: 4),
              Text('${h.fps.taluk}, ${h.fps.district}', style: t.bodyMedium?.copyWith(color: AppColors.textMuted)),
              Text(l.fpsIdLabel(h.fps.id), style: t.bodyMedium?.copyWith(color: AppColors.textMuted)),
              if (h.fps.openingHours != null) Text(l.openingHours(h.fps.openingHours!), style: t.bodyMedium?.copyWith(color: AppColors.textMuted)),
            ]),
          ),
        ]),
      ),
    ]);
  }
}

class _Stat extends StatelessWidget {
  const _Stat({required this.label, required this.value, required this.icon, this.strong = false});
  final String label, value;
  final IconData icon;
  final bool strong;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Semantics(
        label: '$label $value',
        excludeSemantics: true,
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
          decoration: BoxDecoration(color: strong ? AppColors.blueSoft : const Color(0xFFF3F6FB), borderRadius: BorderRadius.circular(14)),
          child: Column(children: [
            Icon(icon, size: 22, color: AppColors.blue),
            const SizedBox(height: 6),
            Text(label, style: const TextStyle(fontSize: 13, color: AppColors.textMuted)),
            const SizedBox(height: 2),
            FittedBox(fit: BoxFit.scaleDown, child: Text(value, style: TextStyle(fontSize: strong ? 18 : 16, fontWeight: FontWeight.w800, color: AppColors.text))),
          ]),
        ),
      ),
    );
  }
}
