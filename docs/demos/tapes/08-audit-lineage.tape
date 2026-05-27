Output docs/demos/gifs/08-audit-lineage.gif

Require zsh
Require python3
Require git

Set Shell "zsh"
Set FontSize 18
Set FontFamily "Berkeley Mono"
Set Width 1280
Set Height 760
Set Padding 28
Set Theme "Rose Pine"
Set TypingSpeed 22ms
Set Framerate 18
Set PlaybackSpeed 1.05
Set WindowBar Colorful

Hide
Type "export PS1='$ '"
Enter
Type "source docs/demos/setup.zsh 08-audit-lineage"
Enter
Type "sigil_demo_make_parser_change"
Enter
Type ", find modified Python files"
Enter
Sleep 700ms
Type ",, run the relevant tests"
Enter
Sleep 1800ms
Type "? review risky changes"
Enter
Sleep 2600ms
Type "clear"
Enter
Show

Type "sigil events"
Enter
Sleep 2100ms
Type "sigil_demo_last_lineage"
Enter
Sleep 2400ms
