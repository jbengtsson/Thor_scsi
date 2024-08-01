#!/bin/sh

prm1=${1-0}

gnuplot << EOP

ps        = $prm1
file_name = "prt_orbit"

f_s = 24
l_w = 2
# Enhanced is needed for Greek characters.
if (ps == 0) \
  set terminal qt 0 enhanced font "Sans, 9" \
else if (ps == 1) \
  set terminal postscript enhanced color solid lw l_w "Times-Roman" f_s; \
  ext = "ps"; \
else if (ps == 2) \
  set terminal postscript eps enhanced color solid lw l_w "Times-Roman" f_s; \
  ext = "eps"; \
else if (ps == 3) \
  set terminal pdf enhanced color solid lw l_w font "Times-Roman f_s"; \
  ext = "pdf"; \
else if (ps == 4) \
  set term pngcairo enhanced color solid lw l_w font "Times-Roman f_s"; \
  ext = "png";

set grid

set style line 1 lt 1 lw 1 lc rgb "blue"
set style line 2 lt 1 lw 1 lc rgb "green"
set style line 3 lt 1 lw 1 lc rgb "red"

if (ps) set output file_name."_1.".(ext);
set title "Horizontal Orbit";
set xlabel "s [m]";
set ylabel "x [mm]";
set y2range [-2.0:20];
plot file_name.".txt" using 3:4 axis x1y2 notitle with fsteps lt 1 lw 1 \
     lc rgb "black", \
     file_name.".txt" using 3:5 title "x" with lines ls 1;
if (!ps) pause mouse "click on graph to cont.\n";

if (ps) set output file_name."_2.".(ext);
set title "Horizontal Divergence";
set xlabel "s [m]";
set ylabel "p_x [mrad]";
set y2range [-2.0:20];
plot file_name.".txt" using 3:4 axis x1y2 notitle with fsteps lt 1 lw 1 \
     lc rgb "black", \
     file_name.".txt" using 3:6 title "x" with lines ls 2;
if (!ps) pause mouse "click on graph to cont.\n";
