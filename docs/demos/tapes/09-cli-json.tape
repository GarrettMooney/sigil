Output docs/demos/gifs/09-cli-json.gif

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
Type "source docs/demos/setup.zsh 09-cli-json"
Enter
Type "clear"
Enter
Show

Type "sigil command --json 'find Python tests'"
Enter
Sleep 1800ms
Type "sigil ask --json 'summarize this repository'"
Enter
Sleep 2200ms
Type "sigil session show --json"
Enter
Sleep 2200ms
