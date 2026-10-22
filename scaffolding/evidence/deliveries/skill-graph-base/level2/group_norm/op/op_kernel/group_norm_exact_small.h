#pragma once
#define GN_DEVICE __aicore__ inline
#include "gn_numeric.h"
#define GN_RSTD_FN __aicore__ inline
#include "exact_rstd_bits.h"

class GroupNormExactSmall {
public:
 __aicore__ inline void Init(GM_ADDR x,GM_ADDR gamma,GM_ADDR beta,GM_ADDR y,const __gm__ GroupNormTilingData* tiling){
  t_=tiling;x_.SetGlobalBuffer(reinterpret_cast<__gm__ uint32_t*>(x),t_->totalLength);
  gamma_.SetGlobalBuffer(reinterpret_cast<__gm__ uint32_t*>(gamma),t_->C);beta_.SetGlobalBuffer(reinterpret_cast<__gm__ uint32_t*>(beta),t_->C);
  y_.SetGlobalBuffer(reinterpret_cast<__gm__ uint32_t*>(y),t_->totalLength);
  pipe_.InitBuffer(x_queue_,1,512);pipe_.InitBuffer(y_queue_,1,512);
 }
 __aicore__ inline void Process(){
  if(t_->dtype!=GN_FLOAT32||t_->groupElements<1||t_->groupElements>128)return;
  const uint64_t first=uint64_t(AscendC::GetBlockIdx())*t_->exactGroupsPerBlock;
  const uint64_t end=first+t_->exactGroupsPerBlock<t_->groupCount?first+t_->exactGroupsPerBlock:t_->groupCount;
  for(uint64_t group=first;group<end;++group)One(group);
 }
private:
 struct Reader{AscendC::LocalTensor<uint32_t> values;uint32_t offset;
  __aicore__ inline uint32_t Get(uint32_t i)const{return values.GetValue(offset+i);}
 };
 struct State{GnNumeric::Moment value;
  __aicore__ inline void Read(uint32_t,GnNumeric::Moment& out)const{out=value;}
  __aicore__ inline void Write(uint32_t,const GnNumeric::Moment& in){value=in;}
 };
 __aicore__ inline void One(uint64_t group){
  const uint32_t length=static_cast<uint32_t>(t_->groupElements),vectors=length/8;
  const uint64_t base=group*t_->groupElements;
  const AscendC::DataCopyExtParams copy{1,length*4,0,0,0};
  auto input=x_queue_.AllocTensor<uint32_t>();
  AscendC::DataCopyPad(input,x_[base],copy,AscendC::DataCopyPadExtParams<uint32_t>{true,0,0,0});
  x_queue_.EnQue(input);input=x_queue_.DeQue<uint32_t>();
  const event_t input_ready=static_cast<event_t>(pipe_.FetchEventID(AscendC::HardEvent::MTE2_S));
  AscendC::SetFlag<AscendC::HardEvent::MTE2_S>(input_ready);AscendC::WaitFlag<AscendC::HardEvent::MTE2_S>(input_ready);
  State state;GnNumeric::Clear(state.value);uint32_t partial[16];
  if(vectors){Reader whole{input,0};GnNumeric::Chunk(whole,vectors,8,partial);GnNumeric::Consume(state,0,0,vectors,8,partial);}
  Reader tail{input,vectors*8};const GnNumeric::Stats stats=GnNumeric::Finish(state,tail,length,8);
  const uint32_t rstd=GnExactRstd::RstdBits(stats.variance,t_->epsilonBits);
  auto output=y_queue_.AllocTensor<uint32_t>();
  const uint32_t first_channel=static_cast<uint32_t>(group%t_->numGroups)*t_->channelsPerGroup;
  uint32_t previous_channel=UINT32_MAX,scale=0,bias=0;
  for(uint32_t i=0;i<length;++i){
   const uint32_t channel=first_channel+static_cast<uint32_t>(uint64_t(i)/t_->spatial);
   if(channel!=previous_channel){scale=GnNumeric::Mul(rstd,gamma_.GetValue(channel));bias=GnNumeric::Fma(scale^0x80000000U,stats.mean,beta_.GetValue(channel));previous_channel=channel;}
   output.SetValue(i,GnNumeric::Fma(scale,input.GetValue(i),bias));
  }
  const event_t scalar_ready=static_cast<event_t>(pipe_.FetchEventID(AscendC::HardEvent::S_MTE3));
  AscendC::SetFlag<AscendC::HardEvent::S_MTE3>(scalar_ready);AscendC::WaitFlag<AscendC::HardEvent::S_MTE3>(scalar_ready);
  y_queue_.EnQue(output);output=y_queue_.DeQue<uint32_t>();
  AscendC::DataCopyPad(y_[base],output,copy);
  const event_t output_done=static_cast<event_t>(pipe_.FetchEventID(AscendC::HardEvent::MTE3_S));
  AscendC::SetFlag<AscendC::HardEvent::MTE3_S>(output_done);AscendC::WaitFlag<AscendC::HardEvent::MTE3_S>(output_done);
  y_queue_.FreeTensor(output);x_queue_.FreeTensor(input);
 }
 const __gm__ GroupNormTilingData* t_;AscendC::TPipe pipe_;
 AscendC::GlobalTensor<uint32_t> x_,gamma_,beta_,y_;
 AscendC::TQue<AscendC::TPosition::VECIN,1> x_queue_;
 AscendC::TQue<AscendC::TPosition::VECOUT,1> y_queue_;
};

extern "C" __global__ __aicore__ __attribute__((aiv)) void group_norm_exact_small(GM_ADDR x,GM_ADDR gamma,GM_ADDR beta,GM_ADDR y,GM_ADDR tiling){
 const __gm__ GroupNormTilingData* t=reinterpret_cast<const __gm__ GroupNormTilingData*>(tiling);
 GroupNormExactSmall kernel;kernel.Init(x,gamma,beta,y,t);kernel.Process();
}
