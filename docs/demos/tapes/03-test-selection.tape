Output docs/demos/gifs/03-test-selection.gif

Require zsh
Require python3
Require git

Set Shell "zsh"
Set FontSize 18
Set FontFamily "Berkeley Mono"
Set Width 1280
Set Height 720
Set Padding 28
Set Theme "Rose Pine"
Set TypingSpeed 22ms
Set Framerate 18
Set PlaybackSpeed 1.05
Set WindowBar Colorful

Hide
Type "export PS1='$ '"
Enter
Type "source docs/demos/setup.zsh 03-test-selection"
Enter
Type "sigil_demo_make_test_change"
Enter
Type "clear"
Enter
Show

Type "git diff --name-only"
Enter
Sleep 900ms
Type ", run the relevant tests"
Enter
Sleep 2400ms
