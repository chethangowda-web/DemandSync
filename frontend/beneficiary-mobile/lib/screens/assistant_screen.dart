import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_client.dart';
import '../core/labels.dart';
import '../core/models.dart';
import '../core/theme.dart';
import '../core/voice.dart';
import '../widgets/common.dart';
import 'entitlement_screen.dart';

/// My PDS Assistant: explains the beneficiary's own records. It is rule-based, answers only from the backend for the
/// signed-in user, and cannot change anything. The screen says so.
class AssistantScreen extends StatefulWidget {
  const AssistantScreen({super.key});

  @override
  State<AssistantScreen> createState() => _AssistantScreenState();
}

class _Message {
  _Message.user(this.text)
      : mine = true,
        answer = null,
        error = false;
  _Message.assistant(this.answer)
      : mine = false,
        text = answer!.answer,
        error = false;
  _Message.failure(this.text)
      : mine = false,
        answer = null,
        error = true;
  final bool mine, error;
  final String text;
  final AssistantAnswer? answer;
}

class _AssistantScreenState extends State<AssistantScreen> {
  final _controller = TextEditingController();
  final _scroll = ScrollController();
  final List<_Message> _messages = [];
  bool _busy = false;
  bool _voiceOn = true;
  IntelSummary? _intel;
  final _voice = VoiceSpeaker();

  @override
  void initState() {
    super.initState();
    // Phase 8: beneficiary-scoped intelligence (own records only, advisory).
    // Failure here must never block the assistant below.
    final api = context.read<ApiClient>();
    Future.microtask(() async {
      try {
        final s = await api.intelSummary();
        if (mounted) setState(() => _intel = s);
      } catch (_) {
        // Silent: the assistant conversation below remains fully usable.
      }
    });
    Future.microtask(() {
      if (mounted) _speak(tr(context).assistantHello);
    });
  }

  void _speak(String text) {
    if (_voiceOn) _voice.speak(text, Localizations.localeOf(context).languageCode);
  }

  @override
  void dispose() {
    _controller.dispose();
    _scroll.dispose();
    _voice.stop();
    super.dispose();
  }

  Future<void> _ask({String? question, String? intent, required String shown}) async {
    if (_busy) return;
    final l = tr(context), api = context.read<ApiClient>();
    final lang = Localizations.localeOf(context).languageCode;
    setState(() {
      _messages.add(_Message.user(shown));
      _busy = true;
    });
    _controller.clear();
    _scrollDown();
    try {
      final a = await api.ask(question: question, intent: intent, language: lang);
      if (mounted) {
        setState(() => _messages.add(_Message.assistant(a)));
        _speak(a.answer);
      }
    } catch (e) {
      if (mounted) setState(() => _messages.add(_Message.failure(errorText(l, e))));
    } finally {
      if (mounted) setState(() => _busy = false);
      _scrollDown();
    }
  }

  void _scrollDown() => WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_scroll.hasClients) _scroll.animateTo(_scroll.position.maxScrollExtent + 200, duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
      });

  void _open(BuildContext context, String? view) {
    final tabs = context.read<TabIndex>();
    switch (view) {
      case 'entitlement':
        Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const EntitlementScreen()));
      case 'track':
        Navigator.of(context).popUntil((r) => r.isFirst);
        tabs.go(1);
      case 'history':
        Navigator.of(context).popUntil((r) => r.isFirst);
        tabs.go(2);
      default: // cycle, plan, profile: the home screen shows all of them
        Navigator.of(context).popUntil((r) => r.isFirst);
        tabs.go(0);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    final chips = <(String, String)>[
      ('ENTITLEMENT', l.chipEntitlement), ('WINDOW', l.chipWindow), ('REQUEST', l.chipRequest),
      ('DISPATCH', l.chipDispatch), ('FPS', l.chipFps), ('CANT_SUBMIT', l.chipCantSubmit),
    ];
    return Scaffold(
      appBar: AppBar(title: Text(l.assistantTitle), actions: [
        IconButton(
          tooltip: _voiceOn ? 'Mute voice' : 'Enable voice',
          icon: Icon(_voiceOn ? Icons.volume_up_rounded : Icons.volume_off_rounded),
          onPressed: () {
            setState(() => _voiceOn = !_voiceOn);
            if (!_voiceOn) _voice.stop();
          },
        ),
      ]),
      body: SafeArea(
        child: Column(children: [
          Container(
            width: double.infinity,
            color: AppColors.blueSoft,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            child: Row(children: [
              const IconBadge(icon: Icons.shield_rounded, color: AppColors.blue, size: 30, iconSize: 16),
              const SizedBox(width: 10),
              Expanded(child: Text(l.assistantNote, style: const TextStyle(fontSize: 13.5))),
            ]),
          ),
          Expanded(
            child: ListView(controller: _scroll, padding: const EdgeInsets.all(16), children: [
              _Bubble(text: l.assistantHello, mine: false),
              if (_intel != null)
                for (final card in _intel!.cards)
                  SectionCard(
                    tone: Tone.info,
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Wrap(crossAxisAlignment: WrapCrossAlignment.center, spacing: 10, runSpacing: 6, children: [
                        Row(mainAxisSize: MainAxisSize.min, children: [
                          const IconBadge(icon: Icons.insights_rounded, color: AppColors.blue, size: 32, iconSize: 17),
                          const SizedBox(width: 10),
                          Text(card.title, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
                        ]),
                        const StatusChip(label: 'ADVISORY', tone: Tone.info, icon: Icons.auto_awesome_rounded),
                      ]),
                      const SizedBox(height: 8),
                      Text(card.summary, style: const TextStyle(fontSize: 14.5, height: 1.4)),
                      if (card.recommendation != null) ...[
                        const SizedBox(height: 6),
                        Text(card.recommendation!, style: const TextStyle(fontSize: 13, color: AppColors.textMuted)),
                      ],
                    ]),
                  ),
              for (final m in _messages)
                _Bubble(
                  text: m.text,
                  mine: m.mine,
                  error: m.error,
                  footer: m.answer == null
                      ? null
                      : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          if (m.answer!.source != null) Text(l.sourceLabel(m.answer!.source!), style: const TextStyle(fontSize: 12.5, color: AppColors.textMuted)),
                          if (m.answer!.view != null) TextButton(onPressed: () => _open(context, m.answer!.view), style: TextButton.styleFrom(minimumSize: const Size(48, 48), padding: EdgeInsets.zero), child: Text(l.viewRelated)),
                        ]),
                ),
              if (_busy) _Bubble(text: l.assistantThinking, mine: false),
            ]),
          ),
          SizedBox(
            height: 56,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              itemCount: chips.length,
              separatorBuilder: (_, __) => const SizedBox(width: 8),
              itemBuilder: (_, i) => ActionChip(label: Text(chips[i].$2), onPressed: _busy ? null : () => _ask(intent: chips[i].$1, shown: chips[i].$2), materialTapTargetSize: MaterialTapTargetSize.padded),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 10),
            child: Row(children: [
              Expanded(
                child: TextField(
                  controller: _controller,
                  textInputAction: TextInputAction.send,
                  maxLength: 300,
                  decoration: InputDecoration(hintText: l.askPlaceholder, counterText: ''),
                  onSubmitted: (v) => v.trim().isEmpty ? null : _ask(question: v.trim(), shown: v.trim()),
                ),
              ),
              const SizedBox(width: 8),
              IconButton.filled(
                onPressed: _busy ? null : () => _controller.text.trim().isEmpty ? null : _ask(question: _controller.text.trim(), shown: _controller.text.trim()),
                icon: const Icon(Icons.send_rounded),
                tooltip: l.send,
                style: IconButton.styleFrom(minimumSize: const Size(56, 56), backgroundColor: AppColors.blue),
              ),
            ]),
          ),
        ]),
      ),
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble({required this.text, required this.mine, this.footer, this.error = false});  final String text;
  final bool mine, error;
  final Widget? footer;

  @override
  Widget build(BuildContext context) {
    final maxWidth = MediaQuery.of(context).size.width * 0.86;
    return Align(
      alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
      child: Semantics(
        liveRegion: !mine,
        child: Container(
          constraints: BoxConstraints(maxWidth: maxWidth),
          margin: const EdgeInsets.only(bottom: 10),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: mine ? AppColors.blue : (error ? AppColors.badSoft : Colors.white),
            borderRadius: BorderRadius.circular(18),
            border: mine ? null : Border.all(color: error ? AppColors.bad.withValues(alpha: 0.3) : AppColors.border),
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(text, style: TextStyle(fontSize: 16.5, height: 1.4, color: mine ? Colors.white : (error ? AppColors.bad : AppColors.text))),
            if (footer != null) ...[const SizedBox(height: 4), footer!],
          ]),
        ),
      ),
    );
  }
}
