#ifndef APROF_GN_EXACT_RSTD_BITS_H
#define APROF_GN_EXACT_RSTD_BITS_H
#include <stdint.h>
#ifndef GN_RSTD_FN
#define GN_RSTD_FN inline
#endif
// RN-even binary64 add -> RN-even binary64 sqrt -> RN-even binary64 reciprocal
// -> RN-even binary32. Integer operations only. Canonical NaN, no FP flags.
namespace GnExactRstd {
static constexpr uint64_t SIGN=0x8000000000000000ULL, INF=0x7ff0000000000000ULL;
static constexpr uint64_t FRAC=0x000fffffffffffffULL, HIDDEN=0x0010000000000000ULL;
static constexpr uint64_t QNAN=0x7ff8000000000000ULL;
GN_RSTD_FN uint32_t Bits32(uint32_t v){
 uint32_t n=0;if(v>=0x10000U){v>>=16;n+=16;}if(v>=0x100U){v>>=8;n+=8;}
 if(v>=16){v>>=4;n+=4;}if(v>=4){v>>=2;n+=2;}if(v>=2){v>>=1;n+=1;}return n+(v!=0);
}
GN_RSTD_FN uint32_t Bits64(uint64_t v){return v>>32 ? 32U+Bits32(uint32_t(v>>32)):Bits32(uint32_t(v));}
GN_RSTD_FN uint32_t Word(const uint32_t*a,uint32_t n,uint32_t i){return i<n?a[i]:0U;}
GN_RSTD_FN uint32_t Right32(const uint32_t*a,uint32_t n,uint32_t bit){
 uint32_t i=bit>>5,s=bit&31U,v=Word(a,n,i)>>s;return s?v|(Word(a,n,i+1)<<(32U-s)):v;
}
GN_RSTD_FN uint64_t Right64(const uint32_t*a,uint32_t n,uint32_t bit){return uint64_t(Right32(a,n,bit))|(uint64_t(Right32(a,n,bit+32))<<32);}
GN_RSTD_FN bool AnyBelow(const uint32_t*a,uint32_t n,uint32_t bit){
 uint32_t whole=bit>>5,tail=bit&31U;for(uint32_t i=0;i<n&&i<whole;++i)if(a[i])return true;
 return tail&&whole<n&&(a[whole]&((1U<<tail)-1U));
}
GN_RSTD_FN void Put32(uint32_t*a,uint32_t n,uint32_t x,uint32_t bit){
 uint32_t i=bit>>5,s=bit&31U;if(i<n)a[i]|=x<<s;if(s&&i+1<n)a[i+1]|=x>>(32U-s);
}
GN_RSTD_FN uint64_t RoundArray64(const uint32_t*a,uint32_t n,int base,uint64_t sign){
 while(n&&a[n-1]==0)--n;if(!n)return sign;
 int top=int((n-1)*32U+Bits32(a[n-1])-1U),e=base+top;if(e>1023)return sign|INF;
 int shift=e>=-1022?top-52:-1074-base;uint64_t q;
 if(shift<=0)q=Right64(a,n,0)<<uint32_t(-shift);
 else {q=Right64(a,n,uint32_t(shift));uint32_t guard=Right32(a,n,uint32_t(shift-1))&1U;
  if(guard&&(AnyBelow(a,n,uint32_t(shift-1))||(q&1ULL)))++q;}
 if(e<-1022)return sign|q;
 if(q==2ULL*HIDDEN){q>>=1;++e;}if(e>1023)return sign|INF;
 return sign|(uint64_t(e+1023)<<52)|(q&FRAC);
}
GN_RSTD_FN uint64_t Add64(uint64_t a,uint64_t b){
 uint64_t aa=a&~SIGN,bb=b&~SIGN,sa=a&SIGN,sb=b&SIGN;
 if(aa>INF||bb>INF)return QNAN;
 if(aa==INF||bb==INF){if(aa==INF&&bb==INF&&sa!=sb)return QNAN;return aa==INF?a:b;}
 if(aa==0&&bb==0)return sa==sb?sa:0ULL;if(aa==0)return b;if(bb==0)return a;
 uint32_t ea=uint32_t(aa>>52),eb=uint32_t(bb>>52);
 uint64_t ma=(aa&FRAC)|(ea?HIDDEN:0ULL),mb=(bb&FRAC)|(eb?HIDDEN:0ULL);
 int pa=ea?int(ea)-1075:-1074,pb=eb?int(eb)-1075:-1074,base=pa<pb?pa:pb;
 uint32_t as=uint32_t(pa-base),bs=uint32_t(pb-base),at=as+Bits64(ma),bt=bs+Bits64(mb);
 uint32_t n=((at>bt?at:bt)+1U+31U)>>5;
 // Worst finite64 exponent span:2098bits pluscarry, at most66words.
 uint32_t x[68],y[68];for(uint32_t i=0;i<n;++i){x[i]=0;y[i]=0;}
 Put32(x,n,uint32_t(ma),as);Put32(x,n,uint32_t(ma>>32),as+32U);
 Put32(y,n,uint32_t(mb),bs);Put32(y,n,uint32_t(mb>>32),bs+32U);
 if(sa==sb){uint32_t carry=0;for(uint32_t i=0;i<n;++i){uint32_t s=x[i]+y[i],c0=s<x[i],t=s+carry,c1=t<s;x[i]=t;carry=c0|c1;}return RoundArray64(x,n,base,sa);}
 int cmp=0;for(uint32_t i=n;i>0;--i)if(x[i-1]!=y[i-1]){cmp=x[i-1]>y[i-1]?1:-1;break;}
 if(cmp==0)return 0ULL;uint32_t*big=cmp>0?x:y;const uint32_t*small=cmp>0?y:x;
 uint32_t borrow=0;for(uint32_t i=0;i<n;++i){uint32_t s=big[i]-small[i],b0=big[i]<small[i],t=s-borrow,b1=s<borrow;big[i]=t;borrow=b0|b1;}
 return RoundArray64(big,n,base,cmp>0?sa:sb);
}
GN_RSTD_FN void DecodePositive(uint64_t u,uint64_t& m,int& e){
 uint32_t be=uint32_t(u>>52);m=(u&FRAC)|(be?HIDDEN:0ULL);e=be?int(be)-1023:-1022;
 while(m<HIDDEN){m<<=1;--e;}
}
GN_RSTD_FN uint64_t Sqrt64(uint64_t u){
 uint64_t a=u&~SIGN;if(a>INF)return QNAN;if(a==0)return u;if(u&SIGN)return QNAN;if(a==INF)return INF;
 uint64_t m;int e;DecodePositive(a,m,e);if(e%2!=0){m<<=1;--e;}
 uint64_t q=0,rem=0;
 // Restoring square root of the106bit integer m<<52, consumed2bits/step.
 for(int j=52;j>=0;--j){uint32_t bit=uint32_t(j*2);uint64_t pair=bit>=52?((m>>(bit-52))&3ULL):0ULL;
  rem=(rem<<2)|pair;uint64_t trial=(q<<2)|1ULL;
  if(rem>=trial){rem-=trial;q=(q<<1)|1ULL;}else q<<=1;}
 // N-q^2=rem. Midpoint square is q^2+q+1/4, so integer rem>q rounds up.
 if(rem>q)++q;int out=e/2;if(q==2ULL*HIDDEN){q>>=1;++out;}
 return (uint64_t(out+1023)<<52)|(q&FRAC);
}
GN_RSTD_FN uint64_t Reciprocal64(uint64_t u){
 uint64_t a=u&~SIGN,sign=u&SIGN;if(a>INF)return QNAN;if(a==0)return sign|INF;if(a==INF)return sign;
 uint64_t m;int e;DecodePositive(a,m,e);uint64_t q=HIDDEN,rem=0;int out=-e;
 if(m!=HIDDEN){out=-e-1;rem=2ULL*HIDDEN-m;for(int bit=51;bit>=0;--bit){rem<<=1;if(rem>=m){rem-=m;q|=1ULL<<bit;}}}
 if(out<-1022){int shift=-1022-out;if(shift>53)return sign;
  uint64_t guard=(q>>(shift-1))&1ULL;bool sticky=(q&((1ULL<<(shift-1))-1ULL))||rem;
  q>>=shift;if(guard&&(sticky||(q&1ULL)))++q;return sign|q;}
 if((rem<<1)>m||((rem<<1)==m&&(q&1ULL)))++q;
 if(q==2ULL*HIDDEN){q>>=1;++out;}if(out>1023)return sign|INF;
 return sign|(uint64_t(out+1023)<<52)|(q&FRAC);
}
GN_RSTD_FN uint64_t From32(uint32_t u){
 uint64_t sign=uint64_t(u>>31)<<63;uint32_t a=u&0x7fffffffU,be=a>>23,m=a&0x7fffffU;
 if(be==255U)return m?QNAN:sign|INF;if(a==0)return sign;int e;
 if(be){m|=0x800000U;e=int(be)-127;}else {e=-126;while(m<0x800000U){m<<=1;--e;}}
 return sign|(uint64_t(e+1023)<<52)|(uint64_t(m&0x7fffffU)<<29);
}
GN_RSTD_FN uint32_t To32(uint64_t u){
 uint64_t a=u&~SIGN;uint32_t sign=uint32_t(u>>63)<<31;if(a>INF)return 0x7fc00000U;if(a==INF)return sign|0x7f800000U;if(a==0)return sign;
 uint64_t m;int e;DecodePositive(a,m,e);if(e>127)return sign|0x7f800000U;
 int shift=e>=-126?29:-97-e;if(shift>53)return sign;
 uint64_t q=m>>shift,rem=m&((1ULL<<shift)-1ULL),half=1ULL<<(shift-1);
 if(rem>half||(rem==half&&(q&1ULL)))++q;if(e<-126)return sign|uint32_t(q);
 if(q==0x1000000ULL){q>>=1;++e;}if(e>127)return sign|0x7f800000U;
 return sign|(uint32_t(e+127)<<23)|(uint32_t(q)&0x7fffffU);
}
GN_RSTD_FN uint32_t RstdBits(uint32_t variance,uint64_t epsilon){return To32(Reciprocal64(Sqrt64(Add64(From32(variance),epsilon))));}
}
#endif
