#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <vector>
struct EngramGateFusionTilingData{
 uint64_t batch,length,hc,hidden,kernel,dilation,stateLen,rows,outputNumel;
 uint64_t rowBlockLength,outputBlockLength;
 float eps,invHidden,invSqrtHidden;
 uint32_t hasState,blockNum;
};
inline uint64_t EngramNumel(const std::vector<uint64_t>&s){uint64_t n=1;for(auto v:s)n*=v;return n;}
inline EngramGateFusionTilingData ComputeEngramGateFusionTiling(
 const std::vector<uint64_t>&keys,const std::vector<uint64_t>&hidden,const std::vector<uint64_t>&value,
 const std::vector<uint64_t>&n1,const std::vector<uint64_t>&n2,const std::vector<uint64_t>&cn,
 const std::vector<uint64_t>&cw,const std::vector<uint64_t>&state,bool hasState,
 uint64_t hcAttr,uint64_t hiddenAttr,uint64_t kernelAttr,uint64_t dilation,float eps,int64_t cores){
 if(keys.size()!=4||hidden!=keys||value.size()!=3||n1.size()!=2||n2!=n1||cn!=n1||cw.size()!=3)
  throw std::invalid_argument("invalid input rank or linked shape");
 const uint64_t B=keys[0],L=keys[1],HC=keys[2],D=keys[3];
 if(!B||!L||!HC||!D||HC!=hcAttr||D!=hiddenAttr||value!=std::vector<uint64_t>{B,L,D}||
    n1!=std::vector<uint64_t>{HC,D}||!kernelAttr||!dilation||cw!=std::vector<uint64_t>{HC*D,1,kernelAttr}||eps<=0.0f)
  throw std::invalid_argument("shape/attribute constraint failed");
 const uint64_t stateLen=(kernelAttr-1)*dilation;
 if(L==1&&!hasState)throw std::invalid_argument("decode L=1 requires conv_state");
 if(hasState&&state!=std::vector<uint64_t>{B,HC*D,stateLen})throw std::invalid_argument("invalid conv_state shape");
 EngramGateFusionTilingData t{};t.batch=B;t.length=L;t.hc=HC;t.hidden=D;t.kernel=kernelAttr;t.dilation=dilation;
 t.stateLen=stateLen;t.rows=B*L*HC;t.outputNumel=t.rows*D;t.eps=eps;t.invHidden=1.0f/float(D);t.invSqrtHidden=1.0f/std::sqrt(float(D));t.hasState=hasState?1U:0U;
 uint64_t available=uint64_t(std::max<int64_t>(1,cores));t.blockNum=uint32_t(std::min<uint64_t>(available,std::max<uint64_t>(1,t.rows)));
 t.rowBlockLength=((t.rows+t.blockNum-1)/t.blockNum+7)/8*8;t.outputBlockLength=((t.outputNumel+t.blockNum-1)/t.blockNum+15)/16*16;return t;
}
