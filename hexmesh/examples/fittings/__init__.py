"""
Fittings: one building block each.

Bends (smooth, mitred, spline), a reducer, a profiled constriction
(stenosis), the tee and wye junctions, and a closure that joins a network
back onto itself.  The bends, the reducer and the loop carry a thin solid
`pipe_wall` layer around the fluid, to show that every fitting takes the
whole layer stack conformally (for conjugate heat transfer; drop the
`.shell(...)` for flow only).  The stenosis, tee and wye are fluid only.
"""
