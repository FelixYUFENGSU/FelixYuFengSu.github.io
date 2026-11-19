---
title: Chess Game Review
summary: A move-by-move chess coach that runs full-strength Stockfish locally. It explains every move in plain English, names the opening as you go, and lets you step through the engine's best line on the board.
---
After a game, I want to know more than "that was a blunder." I want to know *why*, what I should have played instead, and where the game left the opening I thought I was playing. This app is a local game review in the style of chess.com's: paste a game (or import one from chess.com or Lichess) and it walks you through every move.

![A move breakdown: 5. Nxe5 is a blunder](/projects/chess/coach.jpg)

## A coach for every move

Each move gets a short breakdown in a speech bubble:

- **A verdict:** brilliant, great, best, excellent, good, book, inaccuracy, mistake, miss, or blunder. The same badge appears on the board and in the move list.
- **The idea behind the move:** developing a piece, fighting for the center, castling, setting up a fianchetto, creating a threat, or trading.
- **What it allows:** hanging pieces, forks, forced mates, and pieces a move leaves *exposed*. In the sample game above, 5.Nxe5 looks like it wins a pawn, but moving the knight uncovers the queen on d1 to the bishop on g4. That's the classic Légal trap, and the review spells it out.
- **What was better**, with the engine's full line.

None of this comes from a language model. The explanations are generated from the board itself (which pieces attack what before and after the move) combined with the engine's evaluation, so they're deterministic and run entirely locally.

## See the best line on the board

Every move the engine checked shows the best continuation from that position. Click **Show on board**, or any move in the line, and the board jumps there. The arrow keys step through it and Esc brings you back to the game.

![Stepping through the engine's best line](/projects/chess/line.jpg)

## Openings, move by move

The review tracks the opening at every move, using the Lichess opening database, so you can watch the game narrow from *King's Pawn Game* to *Italian Game* to *Italian Game: Paris Defense*. Each move is tagged **In theory** or **Out of book**, and the first move that leaves known theory is called out.

## Honest ratings

My first version rated my own games too kindly, so I made the scoring stricter:

- **A stronger engine.** Analysis uses full-strength Stockfish 18 (the large NNUE network) instead of the lightweight build, searching 18 moves deep on Quick and 24 on Deep.
- **Book moves don't count.** Opening-theory moves were never really judged by the engine, so they no longer pad the accuracy score.
- **Mistakes weigh more.** Similar to Lichess's approach, game accuracy averages the usual mean with the *harmonic* mean of per-move accuracy. The harmonic mean is dominated by the worst moves, so one real blunder can't hide behind thirty easy ones.
- **No free "excellents."** A move that gives up more than a quarter of a pawn while the game is still close can't be rated excellent, even if the win-probability change looks small.

After those changes, a game with a blunder on each side drops from about 89% / 78% accuracy to 67% / 34%, while Kasparov's famous 1999 win over Topalov still scores 92%, with the rook sacrifice 24.Rxd4 rated brilliant.

![Game overview with accuracy and move counts](/projects/chess/overview.jpg)

## How it works

Each move's quality comes from the change in **win probability**, which turns the engine's evaluation (in centipawns) into a percentage:

$$W(c) = 50 + 50\left(\frac{2}{1 + e^{-0.00368\,c}} - 1\right)$$

A move's accuracy decays exponentially with how much win probability it gives away, and the verdicts come from thresholds on that loss, tightened by centipawn limits while the game is undecided.

The app is built with Next.js and TypeScript. Stockfish runs as WebAssembly on the server and streams progress back as each position is analyzed, and chess.js handles the rules and notation.

## Limitations

- Full-strength analysis takes time: about a minute and a half for a 40-move game on Quick, and up to four minutes on Deep.
- Chess.com has never published how it classifies moves, so the "brilliant" and "great" labels approximate its approach rather than copying it exactly.
- Importing a single chess.com game by URL relies on an undocumented endpoint and may break; importing by username uses their public API.
