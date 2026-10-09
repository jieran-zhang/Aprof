#ifndef APROF_SOFT_FMA_BITS_H
#define APROF_SOFT_FMA_BITS_H
#include <stdint.h>
#ifndef APROF_SFMA_FN
#define APROF_SFMA_FN inline
#endif
// Binary32 round-to-nearest, ties-to-even result bits. All arithmetic below is
// unsigned32 or bounded signed32; no FP instructions, uint64, or library calls.
// NaNs return canonical quietNaN; exception flags/NaN payload propagation are not emulated.
namespace AprofSoftFma {
static constexpr uint32_t kWords = 18;
APROF_SFMA_FN uint32_t Bits(uint32_t x) {
    uint32_t n = 0;
    if (x >= 0x10000U) { x >>= 16; n += 16; }
    if (x >= 0x100U) { x >>= 8; n += 8; }
    if (x >= 0x10U) { x >>= 4; n += 4; }
    if (x >= 0x4U) { x >>= 2; n += 2; }
    if (x >= 0x2U) { x >>= 1; n += 1; }
    return n + (x != 0);
}
APROF_SFMA_FN void Put(uint32_t* a, uint32_t n, uint32_t x, uint32_t bit) {
    const uint32_t i = bit >> 5, s = bit & 31U;
    if (i < n) a[i] |= x << s;
    if (s != 0 && i + 1 < n) a[i + 1] |= x >> (32U - s);
}
APROF_SFMA_FN uint32_t Word(const uint32_t* a, uint32_t n, uint32_t i) {
    return i < n ? a[i] : 0U;
}
APROF_SFMA_FN uint32_t RightLow(const uint32_t* a, uint32_t n, uint32_t shift) {
    const uint32_t i = shift >> 5, s = shift & 31U;
    const uint32_t lo = Word(a,n,i) >> s;
    return s == 0 ? lo : lo | (Word(a,n,i+1) << (32U-s));
}
APROF_SFMA_FN bool AnyBelow(const uint32_t* a, uint32_t n, uint32_t bit) {
    const uint32_t whole = bit >> 5, tail = bit & 31U;
    for (uint32_t i=0; i<n && i<whole; ++i) if (a[i] != 0) return true;
    return tail != 0 && whole < n && (a[whole] & ((1U << tail)-1U)) != 0;
}
APROF_SFMA_FN uint32_t Round(const uint32_t* a, uint32_t n, int32_t base, uint32_t sign) {
    while (n != 0 && a[n-1] == 0) --n;
    if (n == 0) return sign;
    const int32_t top = static_cast<int32_t>((n-1)*32U + Bits(a[n-1])-1U);
    int32_t exp = base + top;
    if (exp > 127) return sign | 0x7f800000U;
    const int32_t shift = exp >= -126 ? top-23 : -149-base;
    uint32_t q;
    if (shift <= 0) {
        // top-shift <=23, hence this exact left shift fits24bits and shift>=-23.
        q = a[0] << static_cast<uint32_t>(-shift);
    } else {
        q = RightLow(a,n,static_cast<uint32_t>(shift));
        const uint32_t guard = RightLow(a,n,static_cast<uint32_t>(shift-1)) & 1U;
        if (guard != 0 && (AnyBelow(a,n,static_cast<uint32_t>(shift-1)) || (q & 1U))) ++q;
    }
    if (exp < -126) return sign | q; // q<=2^23: subnormal, zero, or smallest normal.
    if (q == 0x01000000U) { q >>= 1; ++exp; }
    if (exp > 127) return sign | 0x7f800000U;
    return sign | (static_cast<uint32_t>(exp+127)<<23) | (q & 0x007fffffU);
}
APROF_SFMA_FN uint32_t FmaBits(uint32_t a, uint32_t b, uint32_t c) {
    const uint32_t ea=(a>>23)&255U, eb=(b>>23)&255U, ec=(c>>23)&255U;
    const uint32_t fa=a&0x007fffffU, fb=b&0x007fffffU, fc=c&0x007fffffU;
    const uint32_t sp=(a^b)&0x80000000U, sc=c&0x80000000U;
    if ((ea==255U && fa) || (eb==255U && fb) || (ec==255U && fc)) return 0x7fc00000U;
    if (ea==255U || eb==255U) {
        if ((ea==0 && fa==0) || (eb==0 && fb==0)) return 0x7fc00000U;
        if (ec==255U && sp!=sc) return 0x7fc00000U;
        return sp | 0x7f800000U;
    }
    if (ec==255U) return c;
    const uint32_t ma=fa | (ea==0 ? 0U : 0x00800000U);
    const uint32_t mb=fb | (eb==0 ? 0U : 0x00800000U);
    const uint32_t mc=fc | (ec==0 ? 0U : 0x00800000U);
    if (ma==0 || mb==0) return mc!=0 ? c : ((sp==sc) ? sp : 0U);
    const int32_t pe=(ea==0 ? -149 : static_cast<int32_t>(ea)-150)
                    +(eb==0 ? -149 : static_cast<int32_t>(eb)-150);
    const int32_t ce=ec==0 ? -149 : static_cast<int32_t>(ec)-150;
    // Exact24x24->48 multiplication using only32-bit operations.
    const uint32_t a0=ma&65535U, a1=ma>>16, b0=mb&65535U, b1=mb>>16;
    const uint32_t p0=a0*b0;
    const uint32_t mid=(p0>>16)+a0*b1+a1*b0;
    const uint32_t lo=(p0&65535U)|(mid<<16), hi=a1*b1+(mid>>16);
    const int32_t base = mc==0 || pe<ce ? pe : ce;
    const uint32_t ps=static_cast<uint32_t>(pe-base), cs=static_cast<uint32_t>(ce-base);
    const uint32_t pt=ps+(hi==0 ? Bits(lo) : 32U+Bits(hi));
    const uint32_t ct=mc==0 ? 0U : cs+Bits(mc);
    // At most554 significant positions plus1carry;18limbs suffice.
    const uint32_t n=((pt>ct ? pt : ct)+1U+31U)>>5;
    uint32_t p[kWords], d[kWords];
    for (uint32_t i=0; i<n; ++i) { p[i]=0; d[i]=0; }
    Put(p,n,lo,ps); Put(p,n,hi,ps+32U); if (mc!=0) Put(d,n,mc,cs);
    if (sp==sc || mc==0) {
        uint32_t carry=0;
        for (uint32_t i=0; i<n; ++i) {
            const uint32_t sum=p[i]+d[i], c0=sum<p[i];
            const uint32_t sum2=sum+carry, c1=sum2<sum;
            p[i]=sum2; carry=c0|c1;
        }
        return Round(p,n,base,sp);
    }
    int32_t cmp=0;
    for (uint32_t i=n; i>0; --i) if (p[i-1]!=d[i-1]) { cmp=p[i-1]>d[i-1] ? 1 : -1; break; }
    if (cmp==0) return 0U; // Exact nonzero cancellation yields+0 in RN-even.
    uint32_t* big=cmp>0 ? p : d; const uint32_t* small=cmp>0 ? d : p;
    uint32_t borrow=0;
    for (uint32_t i=0; i<n; ++i) {
        const uint32_t diff=big[i]-small[i], b0=big[i]<small[i];
        const uint32_t diff2=diff-borrow, b1=diff<borrow;
        big[i]=diff2; borrow=b0|b1;
    }
    return Round(big,n,base,cmp>0 ? sp : sc);
}
}
#endif
