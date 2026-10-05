import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { firstValueFrom, Subject } from 'rxjs'

const BACKEND_URL = 'http://localhost:5001'

export interface State {
  steps: number
  done: {
    __all__: boolean
    [key: string]: boolean
  }
}

@Injectable({
  providedIn: 'root',
})
export class ControllerService {
  private resetEvent = new Subject<void>()

  /** Emits when user selects a new link in the link-map dropdown. */
  public readonly linkChange = new Subject<string>()

  constructor(private http: HttpClient) {}

  public stepEnv(policyIndex: number = 0) {
    return firstValueFrom(
      this.http.post<any>(`${BACKEND_URL}/control`, { command: 'start' })
    ).then(() => 0)
  }

  public resetEnv() {
    return firstValueFrom(
      this.http.post<any>(`${BACKEND_URL}/control`, { command: 'reset' })
    ).then((state) => {
      this.resetEvent.next()
      return state as State
    })
  }

  public observeReset() {
    return this.resetEvent.asObservable()
  }

  /** Called by link-map component when user selects a link from the dropdown. */
  public selectLink(link: string) {
    this.linkChange.next(link)
  }
}
