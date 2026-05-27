Output docs/demos/gifs/05-patch-preview.gif

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
Set TypingSpeed 20ms
Set Framerate 18
Set PlaybackSpeed 1.05
Set WindowBar Colorful

Hide
Type "export PS1='$ '"
Enter
Type "source docs/demos/setup.zsh 05-patch-preview"
Enter
Type "clear"
Enter
Show

Type ",, fix parse_value with the smallest boxed patch"
Enter
Sleep 1400ms
Type "n"
Enter
Sleep 900ms
Type "sigil patch show"
Enter
Sleep 1800ms
Type "sigil patch check"
Enter
Sleep 900ms
Type "sigil patch apply --yes"
Enter
Sleep 1200ms

