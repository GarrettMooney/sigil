Output docs/demos/gifs/01-command-proposal.gif

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
Type "source docs/demos/setup.zsh 01-command-proposal"
Enter
Type "clear"
Enter
Show

Type ", find files over 10 MB in this repo excluding .git"
Enter
Sleep 1800ms
Type "find . -path ./.git -prune -o -type f -size +10M -print"
Enter
Sleep 1500ms

