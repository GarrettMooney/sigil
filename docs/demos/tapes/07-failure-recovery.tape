Output docs/demos/gifs/07-failure-recovery.gif

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
Type "source docs/demos/setup.zsh 07-failure-recovery"
Enter
Type "clear"
Enter
Show

Type "git push"
Enter
Sleep 900ms
Type "? why did this git command fail?"
Enter
Sleep 1700ms
Type "?? what is the safest next command?"
Enter
Sleep 1700ms

