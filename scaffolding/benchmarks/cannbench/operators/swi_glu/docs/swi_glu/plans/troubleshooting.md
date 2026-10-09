# Troubleshooting

No non-trivial implementation failure was encountered. The important design
constraint was clipping each output tile at `segmentLength`; without that clip,
a DMA tile crossing an outer-group boundary would read the wrong half of the
next group.
