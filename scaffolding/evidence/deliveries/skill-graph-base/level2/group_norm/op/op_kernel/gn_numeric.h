#pragma once
#include <stdint.h>
#ifndef GN_DEVICE
#define GN_DEVICE inline
#endif
#ifndef APROF_SFMA_FN
#define APROF_SFMA_FN GN_DEVICE
#endif
#include "soft_fma_bits.h"

// Pure integer, CPU/device-shared binary32 arithmetic. No floating contraction,
// vector FMA, reciprocal, sqrt, float conversions, or denormal ISA assumption.
namespace GnNumeric {
GN_DEVICE uint32_t Add(uint32_t a,uint32_t b){return AprofSoftFma::FmaBits(a,0x3f800000U,b);}
GN_DEVICE uint32_t Sub(uint32_t a,uint32_t b){return Add(a,b^0x80000000U);}
GN_DEVICE uint32_t Mul(uint32_t a,uint32_t b){return AprofSoftFma::FmaBits(a,b,(a^b)&0x80000000U);}
GN_DEVICE uint32_t Fma(uint32_t a,uint32_t b,uint32_t c){return AprofSoftFma::FmaBits(a,b,c);}
GN_DEVICE uint32_t Div(uint32_t a,uint32_t b){
 const uint32_t sign=(a^b)&0x80000000U;uint32_t ax=a&0x7fffffffU,bx=b&0x7fffffffU;
 if(ax>0x7f800000U||bx>0x7f800000U||(ax==0&&bx==0)||(ax==0x7f800000U&&bx==0x7f800000U))return 0x7fc00000U;
 if(ax==0x7f800000U||bx==0)return sign|0x7f800000U;
 if(ax==0||bx==0x7f800000U)return sign;
 int ea=int(ax>>23),eb=int(bx>>23);uint32_t ma=ax&0x7fffffU,mb=bx&0x7fffffU;
 if(ea){ma|=0x800000U;ea-=127;}else{ea=-126;while(ma<0x800000U){ma<<=1;--ea;}}
 if(eb){mb|=0x800000U;eb-=127;}else{eb=-126;while(mb<0x800000U){mb<<=1;--eb;}}
 int exponent=ea-eb;if(ma<mb){ma<<=1;--exponent;}
 uint32_t q=0x800000U,rem=ma-mb;
 for(int bit=22;bit>=0;--bit){rem<<=1;if(rem>=mb){rem-=mb;q|=uint32_t(1)<<bit;}}
 if(exponent<-126){int shift=-126-exponent;if(shift>24)return sign;
  const uint32_t guard=(q>>(shift-1))&1U;const bool sticky=(q&((uint32_t(1)<<(shift-1))-1U))!=0||rem!=0;
  q>>=shift;if(guard&&(sticky||(q&1U)))++q;return sign|q;
 }
 if((rem<<1)>mb||((rem<<1)==mb&&(q&1U)))++q;
 if(q==0x1000000U){q>>=1;++exponent;}if(exponent>127)return sign|0x7f800000U;
 return sign|(uint32_t(exponent+127)<<23)|(q&0x7fffffU);
}
GN_DEVICE uint32_t FromCount(uint64_t n){
 if(!n)return 0;int e=0;uint64_t tmp=n;while(tmp>>=1)++e;
 uint64_t q=e<=23?n<<(23-e):n>>(e-23);
 if(e>23){int shift=e-23;uint64_t rem=n&((uint64_t(1)<<shift)-1),half=uint64_t(1)<<(shift-1);
  if(rem>half||(rem==half&&(q&1)))++q;if(q==(uint64_t(1)<<24)){q>>=1;++e;}}
 return (uint32_t(e+127)<<23)|(uint32_t(q)&0x7fffffU);
}
struct Moment{uint64_t count;uint32_t mean[8],square[8];};
GN_DEVICE void Clear(Moment& value){value.count=0;for(int k=0;k<8;++k){value.mean[k]=0;value.square[k]=0;}}
GN_DEVICE void Merge(Moment& a,uint64_t count,const uint32_t* mean,const uint32_t* square){
 const uint64_t total=a.count+count;const uint32_t coefficient=total?Div(FromCount(count),FromCount(total)):0;
 for(int k=0;k<8;++k){const uint32_t delta=Sub(mean[k],a.mean[k]);
  const uint32_t sum=Add(a.square[k],square[k]),weighted=Mul(coefficient,delta),old_delta=Mul(delta,FromCount(a.count));
  a.mean[k]=Add(a.mean[k],weighted);a.square[k]=Fma(old_delta,weighted,sum);}
 a.count=total;
}
GN_DEVICE uint32_t Depth(uint64_t chunks){uint32_t depth=0;uint64_t power=1;while(power<chunks){power<<=1;++depth;}return depth;}
template<class Reader>GN_DEVICE void Chunk(const Reader& input,uint32_t vectors,uint32_t K,uint32_t* record){
 for(uint32_t i=0;i<2*K;++i)record[i]=0;
 for(uint32_t j=0;j<vectors;++j){const uint32_t coefficient=Div(0x3f800000U,FromCount(j+1));
  for(uint32_t half=0;half<K/8;++half)for(uint32_t lane=0;lane<8;++lane){
   uint32_t* mean=record+half*16;uint32_t* square=mean+8;const uint32_t value=input.Get(j*K+half*8+lane),delta=Sub(value,mean[lane]);
   mean[lane]=Fma(coefficient,delta,mean[lane]);square[lane]=Fma(delta,Sub(value,mean[lane]),square[lane]);}}
}
template<class State>GN_DEVICE void Consume(State& state,uint64_t chunk,uint32_t depth,uint32_t count,uint32_t K,const uint32_t* record){
 Moment current;state.Read(0,current);
 for(uint32_t half=0;half<K/8;++half)Merge(current,count,record+half*16,record+half*16+8);
 state.Write(0,current);
 uint64_t mask=chunk+1;
 for(uint32_t j=1;j<depth&&(mask&1U)==0;++j){Moment previous;state.Read(j-1,previous);state.Read(j,current);
  Merge(current,previous.count,previous.mean,previous.square);state.Write(j,current);Clear(previous);state.Write(j-1,previous);mask>>=1;}
}
struct Stats{uint32_t mean,variance;};
template<class State,class Reader>GN_DEVICE Stats Finish(State& state,const Reader& tail,uint64_t length,uint32_t K){
 const uint64_t vectors=length/K,chunks=(vectors+15)/16;const uint32_t depth=Depth(chunks);
 Moment merged;state.Read(0,merged);
 for(uint32_t j=1;j<depth;++j){Moment previous;state.Read(j,previous);Merge(merged,previous.count,previous.mean,previous.square);}
 uint64_t count=0;uint32_t mean=0,variance=0;
 for(uint32_t i=0;i<length%K;++i){uint32_t value=tail.Get(i),delta=Sub(value,mean);++count;
  mean=Add(mean,Div(delta,FromCount(count)));variance=Fma(delta,Sub(value,mean),variance);}
 const uint64_t lane_count=vectors*K/8;
 for(uint32_t lane=0;lane<8;++lane){uint64_t total=count+lane_count;uint32_t coefficient=total?Div(FromCount(lane_count),FromCount(total)):0;
  const uint32_t delta=Sub(merged.mean[lane],mean);mean=Fma(coefficient,delta,mean);
  variance=Add(variance,Fma(Mul(Mul(delta,delta),coefficient),FromCount(count),merged.square[lane]));count=total;}
 return {mean,Div(variance,FromCount(length))};
}

} // namespace GnNumeric
