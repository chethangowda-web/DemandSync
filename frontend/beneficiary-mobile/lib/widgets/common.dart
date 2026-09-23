import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_exception.dart';
import '../core/labels.dart';
import '../core/session.dart';
import '../core/theme.dart';
import '../l10n/generated/app_localizations.dart';

AppLocalizations tr(BuildContext c) => AppLocalizations.of(c);

/// Runs [load], and renders loading, error (with retry) and success. Reloads when [session.refreshTick] changes
/// so a submitted plan or a cancelled plan is reflected everywhere without manual refreshing.
class AsyncBody<T> extends StatefulWidget {
  const AsyncBody({super.key, required this.load, required this.builder});

  final Future<T> Function() load;
  final Widget Function(BuildContext context, T data, Future<void> Function() reload) builder;

  @override
  State<AsyncBody<T>> createState() => _AsyncBodyState<T>();
}

class _AsyncBodyState<T> extends State<AsyncBody<T>> {
  late Future<T> _future;
  int _tick = -1;

  @override
  void initState() {
    super.initState();
    _future = widget.load();
  }

  Future<void> _reload() async {
    final f = widget.load();
    setState(() {
      _future = f;
    });
    try {
      await f;
    } catch (_) {/* shown by the builder below */}
  }

  @override
  Widget build(BuildContext context) {
    final tick = context.select<SessionController, int>((s) => s.refreshTick);
    if (_tick != -1 && tick != _tick) {
      _future = widget.load();
    }
    _tick = tick;
    final l = tr(context);
    return FutureBuilder<T>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return Center(child: Semantics(label: l.loading, child: const CircularProgressIndicator()));
        }
        if (snap.hasError) {
          return ErrorView(error: snap.error!, onRetry: _reload);
        }
        return widget.builder(context, snap.data as T, _reload);
      },
    );
  }
}

class ErrorView extends StatelessWidget {
  const ErrorView({super.key, required this.error, required this.onRetry});
  final Object error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    final offline = error is ApiException && ((error as ApiException).kind == ApiErrorKind.offline || (error as ApiException).kind == ApiErrorKind.timeout);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Icon(offline ? Icons.wifi_off_rounded : Icons.error_outline_rounded, size: 56, color: AppColors.textMuted),
          const SizedBox(height: 16),
          Text(errorText(l, error), textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodyLarge),
          const SizedBox(height: 20),
          BigButton(label: l.retry, icon: Icons.refresh_rounded, onPressed: onRetry, expand: false),
        ]),
      ),
    );
  }
}

enum Tone { good, info, warn, bad, neutral }

({Color fg, Color bg}) toneColors(Tone t) => switch (t) {
      Tone.good => (fg: AppColors.good, bg: AppColors.goodSoft),
      Tone.info => (fg: AppColors.blue, bg: AppColors.blueSoft),
      Tone.warn => (fg: AppColors.warn, bg: AppColors.warnSoft),
      Tone.bad => (fg: AppColors.bad, bg: AppColors.badSoft),
      Tone.neutral => (fg: AppColors.textMuted, bg: const Color(0xFFEDF1F7)),
    };

/// A status is always icon + words, so it never depends on colour to be understood.
class StatusChip extends StatelessWidget {
  const StatusChip({super.key, required this.label, required this.tone, this.icon});
  final String label;
  final Tone tone;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final c = toneColors(tone);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(color: c.bg, borderRadius: BorderRadius.circular(999)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        if (icon != null) ...[Icon(icon, size: 16, color: c.fg), const SizedBox(width: 6)],
        Flexible(child: Text(label, style: TextStyle(color: c.fg, fontWeight: FontWeight.w700, fontSize: 13))),
      ]),
    );
  }
}

Tone toneForStatusKey(String? key) => switch (key) {
      'COLLECTED' || 'AVAILABLE_FOR_COLLECTION' || 'RECEIVED_AT_FPS' => Tone.good,
      'CHOICE_WINDOW_CLOSED' => Tone.warn,
      null => Tone.neutral,
      _ => Tone.info,
    };

class SectionCard extends StatelessWidget {
  const SectionCard({super.key, required this.child, this.onTap, this.padding = const EdgeInsets.all(18), this.tone});
  final Widget child;
  final VoidCallback? onTap;
  final EdgeInsets padding;
  final Tone? tone;

  @override
  Widget build(BuildContext context) {
    final bg = tone == null ? AppColors.surface : toneColors(tone!).bg;
    return Card(
      elevation: 0,
      color: bg,
      margin: const EdgeInsets.only(bottom: 14),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: BorderSide(color: tone == null ? AppColors.border : toneColors(tone!).fg.withValues(alpha: 0.25)),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(onTap: onTap, child: Padding(padding: padding, child: child)),
    );
  }
}

enum BigButtonStyle { primary, secondary, danger }

/// 56dp tall (comfortably above the 48dp minimum), full width by default, with a real text label.
class BigButton extends StatelessWidget {
  const BigButton({super.key, required this.label, required this.onPressed, this.icon, this.style = BigButtonStyle.primary,
      this.loading = false, this.expand = true});
  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final BigButtonStyle style;
  final bool loading;
  final bool expand;

  @override
  Widget build(BuildContext context) {
    final content = Row(mainAxisSize: MainAxisSize.min, mainAxisAlignment: MainAxisAlignment.center, children: [
      if (loading)
        const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2.5, color: Colors.white))
      else if (icon != null)
        Icon(icon, size: 22),
      if (loading || icon != null) const SizedBox(width: 10),
      Flexible(child: Text(label, textAlign: TextAlign.center)),
    ]);
    final size = Size(expand ? double.infinity : 0, 56);
    final shape = RoundedRectangleBorder(borderRadius: BorderRadius.circular(16));
    final enabled = loading ? null : onPressed;
    final button = switch (style) {
      BigButtonStyle.primary => FilledButton(
          onPressed: enabled,
          style: FilledButton.styleFrom(minimumSize: size, shape: shape, backgroundColor: AppColors.blue, textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
          child: content),
      BigButtonStyle.secondary => OutlinedButton(
          onPressed: enabled,
          style: OutlinedButton.styleFrom(minimumSize: size, shape: shape, foregroundColor: AppColors.blue, side: const BorderSide(color: AppColors.blue, width: 1.5), textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
          child: content),
      BigButtonStyle.danger => OutlinedButton(
          onPressed: enabled,
          style: OutlinedButton.styleFrom(minimumSize: size, shape: shape, foregroundColor: AppColors.bad, side: const BorderSide(color: AppColors.bad, width: 1.5), textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
          child: content),
    };
    return button;
  }
}

/// A filled colour circle carrying a single icon — the recurring "badge" motif used across the
/// redesigned screens (home, entitlement, plan, track, ...) so every card reads as one family.
class IconBadge extends StatelessWidget {
  const IconBadge({super.key, required this.icon, this.color = AppColors.blue, this.size = 38, this.iconSize});
  final IconData icon;
  final Color color;
  final double size;
  final double? iconSize;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
      child: Icon(icon, color: Colors.white, size: iconSize ?? size * 0.52),
    );
  }
}

/// The "ICON · EYEBROW TITLE · subtitle" row that opens most redesigned section cards, matching the
/// pattern established on the home screen (PLAN YOUR RATION COLLECTION, VERIFY YOUR ENTITLEMENT, ...).
class SectionHeader extends StatelessWidget {
  const SectionHeader({super.key, required this.icon, required this.title, this.subtitle, this.badgeColor = AppColors.blue, this.trailing});
  final IconData icon;
  final String title;
  final String? subtitle;
  final Color badgeColor;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final row = Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      IconBadge(icon: icon, color: badgeColor),
      const SizedBox(width: 12),
      Expanded(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(title.toUpperCase(), style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 13, color: AppColors.navy, letterSpacing: 0.4)),
          if (subtitle != null) ...[
            const SizedBox(height: 2),
            Text(subtitle!, style: const TextStyle(color: AppColors.textMuted, fontSize: 13)),
          ],
        ]),
      ),
    ]);
    if (trailing == null) return row;
    return LayoutBuilder(builder: (context, c) {
      final narrow = c.maxWidth < 420 || MediaQuery.textScaleFactorOf(context) > 1.4;
      if (narrow) {
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [row, const SizedBox(height: 10), trailing!]);
      }
      return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [Expanded(child: row), const SizedBox(width: 8), trailing!]);
    });
  }
}

/// A soft-tint pill button used for secondary in-card actions (View details, Track my ration, ...).
class PillLink extends StatelessWidget {
  const PillLink({super.key, required this.label, required this.onTap, this.icon = Icons.chevron_right_rounded, this.color = AppColors.navy});
  final String label;
  final VoidCallback onTap;
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(999),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
        decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(999), border: Border.all(color: AppColors.border)),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Flexible(child: Text(label, style: TextStyle(color: color, fontWeight: FontWeight.w700, fontSize: 13))),
          const SizedBox(width: 4),
          Icon(icon, size: 16, color: color),
        ]),
      ),
    );
  }
}

class KeyValueRow extends StatelessWidget {
  const KeyValueRow({super.key, required this.label, required this.value, this.strong = false});
  final String label, value;
  final bool strong;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Expanded(flex: 5, child: Text(label, style: t.bodyMedium?.copyWith(color: AppColors.textMuted))),
        const SizedBox(width: 12),
        Expanded(flex: 6, child: Text(value, textAlign: TextAlign.end, style: (strong ? t.titleMedium : t.bodyMedium)?.copyWith(fontWeight: FontWeight.w700))),
      ]),
    );
  }
}

/// Opens the language picker. English, Hindi and Kannada are shown in their own scripts.
class LanguageButton extends StatelessWidget {
  const LanguageButton({super.key, this.light = true});
  final bool light;

  static const names = {'en': 'English', 'hi': 'हिन्दी', 'kn': 'ಕನ್ನಡ'};

  static Future<void> pick(BuildContext context) async {
    final session = context.read<SessionController>();
    final l = tr(context);
    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (ctx) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Padding(padding: const EdgeInsets.all(8), child: Text(l.language, style: Theme.of(ctx).textTheme.titleLarge)),
          for (final loc in SessionController.supportedLocales)
            ListTile(
              minTileHeight: 60,
              leading: Icon(session.locale == loc ? Icons.radio_button_checked : Icons.radio_button_off, color: AppColors.blue),
              title: Text(names[loc.languageCode]!, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
              onTap: () {
                session.setLocale(loc);
                Navigator.pop(ctx);
              },
            ),
        ]),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    final code = context.select<SessionController, String>((s) => s.locale.languageCode);
    return TextButton.icon(
      onPressed: () => pick(context),
      icon: Icon(Icons.translate_rounded, color: light ? Colors.white : AppColors.blue),
      label: Text(names[code]!, style: TextStyle(color: light ? Colors.white : AppColors.blue, fontWeight: FontWeight.w700)),
      style: TextButton.styleFrom(minimumSize: const Size(48, 48)),
      // the visible name is already a full label; add the purpose for screen readers
      key: ValueKey('${l.language}-$code'),
    );
  }
}

/// Which bottom-navigation tab is showing. Held above the Navigator so screens pushed on top of the Shell
/// (a receipt, for example) can still send the user to "My Ration".
class TabIndex extends ChangeNotifier {
  int _index = 0;
  int get index => _index;

  void go(int i) {
    if (i == _index) return;
    _index = i;
    notifyListeners();
  }
}

class BrandMark extends StatelessWidget {
  const BrandMark({super.key, this.size = 72, this.onDark = true});
  final double size;
  final bool onDark;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(color: onDark ? Colors.white : AppColors.blue, borderRadius: BorderRadius.circular(size * 0.28)),
      child: Icon(Icons.grass_rounded, size: size * 0.58, color: onDark ? AppColors.blue : Colors.white),
    );
  }
}

Future<bool> confirmDialog(BuildContext context, {required String title, String? body, required String yes, required String no, bool danger = false}) async {
  final r = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text(title),
      content: body == null ? null : Text(body),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx, false), style: TextButton.styleFrom(minimumSize: const Size(64, 48)), child: Text(no)),
        FilledButton(
          onPressed: () => Navigator.pop(ctx, true),
          style: FilledButton.styleFrom(minimumSize: const Size(64, 48), backgroundColor: danger ? AppColors.bad : AppColors.blue),
          child: Text(yes),
        ),
      ],
    ),
  );
  return r ?? false;
}

void showMessage(BuildContext context, String text) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(text), behavior: SnackBarBehavior.floating, duration: const Duration(seconds: 4)));
}
